import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import {
  // Core Navigation & Actions
  PlayIcon,
  PauseIcon,
  StopIcon,
  ArrowPathIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  XMarkIcon,
  CheckIcon,
  PlusIcon,
  UserCircleIcon,

  // Status & Alerts
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ShieldExclamationIcon,
  ClockIcon,
  BoltIcon,

  // File & Code
  DocumentTextIcon,
  CodeBracketIcon,
  DocumentDuplicateIcon,
  PencilSquareIcon,
  TrashIcon,

  // Communication & Feedback
  ChatBubbleLeftRightIcon,
  ChatBubbleOvalLeftEllipsisIcon,
  PaperAirplaneIcon,
  LightBulbIcon,

  // Terminal & System
  CommandLineIcon,
  CpuChipIcon,
  ServerStackIcon,
  CircleStackIcon,
  EyeIcon,

  // Misc
  MagnifyingGlassIcon,
  ArrowsPointingOutIcon,
  ListBulletIcon,
  SignalIcon,
} from '@heroicons/react/24/outline';
import { PageSkeleton } from './ui/LoadingSkeleton';
import { RealTimeExecutionPanel } from './execution';
import { useToast } from './ui/Toast';

// =============================================================================
// DESIGN DOCUMENTATION
// =============================================================================
/**
 * AGENT MANAGER VIEW - UI/UX SPECIFICATION
 * =========================================
 *
 * PURPOSE:
 * Provide transparency into autonomous agent workflows, allowing developers to
 * review and approve each step, ensuring trust and safety in AI-driven operations.
 *
 * INFORMATION ARCHITECTURE:
 *
 * 1. MANAGER VIEW (Pre-flight Checklist)
 *    - Agent's thought process display (reasoning chain)
 *    - Planned file modifications with diff preview
 *    - Intended terminal commands with risk assessment
 *    - Approve/Reject/Modify controls
 *    - Inline feedback before execution
 *
 * 2. MISSION CONTROL (Real-time Observation)
 *    - Live thinking stream during execution
 *    - Navigation breadcrumb (decision tree visualization)
 *    - Issue highlighting (destructive commands, errors)
 *    - Log streaming panel
 *    - Pause/Resume/Abort controls
 *
 * 3. ARTIFACTS PANEL (Structured Deliverables)
 *    - Task Plan: High-level breakdown
 *    - Implementation Plan: Technical details
 *    - Post-execution Walkthrough: What was done
 *    - Reasoning Documentation: Why decisions were made
 *    - Audit Trail: Task-level abstraction
 *
 * 4. FEEDBACK INTEGRATION
 *    - Inline feedback on artifacts
 *    - Feedback history timeline
 *    - Improvement tracking
 *    - Continuous learning loop
 *
 * VISUAL DESIGN PRINCIPLES:
 * - Apple-inspired clean aesthetic
 * - Clear visual hierarchy for complex information
 * - Progressive disclosure of details
 * - Color coding for risk/status
 * - Generous whitespace
 * - Smooth transitions (200-300ms)
 *
 * ACCESSIBILITY:
 * - WCAG 2.1 AA compliant
 * - Keyboard navigation
 * - Screen reader friendly
 * - 4.5:1 minimum contrast
 * - Focus indicators
 */

// =============================================================================
// DESIGN SYSTEM STYLES
// =============================================================================

const RISK_LEVELS = {
  low: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    border: 'border-olive-300 dark:border-olive-700',
    bg: 'bg-olive-50 dark:bg-olive-900/10',
    icon: 'text-olive-500',
    label: 'Low Risk',
  },
  medium: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    border: 'border-warning-300 dark:border-warning-700',
    bg: 'bg-warning-50 dark:bg-warning-900/10',
    icon: 'text-warning-500',
    label: 'Medium Risk',
  },
  high: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    border: 'border-critical-300 dark:border-critical-700',
    bg: 'bg-critical-50 dark:bg-critical-900/10',
    icon: 'text-critical-500',
    label: 'High Risk',
  },
};

const EXECUTION_STATUS = {
  pending: {
    badge: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
    icon: ClockIcon,
    label: 'Pending',
    dot: 'bg-surface-400',
  },
  thinking: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    icon: CpuChipIcon,
    label: 'Thinking',
    dot: 'bg-aura-500 animate-pulse',
  },
  executing: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    icon: BoltIcon,
    label: 'Executing',
    dot: 'bg-warning-500 animate-pulse',
  },
  paused: {
    badge: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
    icon: PauseIcon,
    label: 'Paused',
    dot: 'bg-surface-500',
  },
  completed: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    icon: CheckCircleIcon,
    label: 'Completed',
    dot: 'bg-olive-500',
  },
  failed: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    icon: XCircleIcon,
    label: 'Failed',
    dot: 'bg-critical-500',
  },
  awaiting_approval: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    icon: EyeIcon,
    label: 'Awaiting Approval',
    dot: 'bg-aura-500',
  },
};

const ACTION_TYPES = {
  file_read: { icon: DocumentTextIcon, label: 'Read File', color: 'aura' },
  file_write: { icon: PencilSquareIcon, label: 'Write File', color: 'warning' },
  file_delete: { icon: TrashIcon, label: 'Delete File', color: 'critical' },
  file_create: { icon: PlusIcon, label: 'Create File', color: 'olive' },
  command: { icon: CommandLineIcon, label: 'Run Command', color: 'warning' },
  api_call: { icon: ServerStackIcon, label: 'API Call', color: 'aura' },
  query: { icon: CircleStackIcon, label: 'Database Query', color: 'olive' },
};

// =============================================================================
// MOCK DATA FOR DEMONSTRATION
// =============================================================================

const MOCK_AGENT_SESSION = {
  id: 'session-001',
  agentName: 'Coder Agent Alpha',
  agentType: 'coder',
  taskDescription: 'Fix SQL injection vulnerability in UserController.java',
  status: 'awaiting_approval',
  startedAt: '2024-12-08T10:30:00Z',

  // Pre-flight checklist data
  thoughtProcess: [
    {
      id: 'thought-1',
      type: 'analysis',
      content: 'Analyzing the vulnerability report and identifying affected code locations...',
      timestamp: '2024-12-08T10:30:05Z',
    },
    {
      id: 'thought-2',
      type: 'planning',
      content: 'The SQL injection occurs in getUserById() method where user input is directly concatenated into the SQL query. I need to replace string concatenation with parameterized queries.',
      timestamp: '2024-12-08T10:30:15Z',
    },
    {
      id: 'thought-3',
      type: 'decision',
      content: 'I will use PreparedStatement with parameterized queries to prevent SQL injection. This is the industry-standard approach and maintains database compatibility.',
      timestamp: '2024-12-08T10:30:25Z',
    },
    {
      id: 'thought-4',
      type: 'risk_assessment',
      content: 'Risk assessment: LOW. The changes are isolated to query construction and do not affect business logic. Existing tests should pass after modification.',
      timestamp: '2024-12-08T10:30:35Z',
    },
  ],

  plannedActions: [
    {
      id: 'action-1',
      type: 'file_read',
      target: 'src/controllers/UserController.java',
      description: 'Read current implementation to understand context',
      risk: 'low',
      status: 'completed',
    },
    {
      id: 'action-2',
      type: 'file_write',
      target: 'src/controllers/UserController.java',
      description: 'Replace string concatenation with PreparedStatement',
      risk: 'medium',
      status: 'pending',
      diff: {
        additions: 8,
        deletions: 4,
        preview: `@@ -45,10 +45,16 @@ public class UserController {
     public User getUserById(String userId) {
-        String query = "SELECT * FROM users WHERE id = '" + userId + "'";
-        return db.executeQuery(query);
+        // Use parameterized query to prevent SQL injection
+        String query = "SELECT * FROM users WHERE id = ?";
+        PreparedStatement stmt = db.prepareStatement(query);
+        stmt.setString(1, userId);
+        return db.executeQuery(stmt);
     }`,
      },
    },
    {
      id: 'action-3',
      type: 'file_write',
      target: 'src/tests/UserControllerTest.java',
      description: 'Add test case for SQL injection prevention',
      risk: 'low',
      status: 'pending',
      diff: {
        additions: 15,
        deletions: 0,
        preview: `@@ -100,6 +100,21 @@ public class UserControllerTest {
+    @Test
+    public void testSqlInjectionPrevention() {
+        // Attempt SQL injection
+        String maliciousInput = "'; DROP TABLE users; --";
+        User result = controller.getUserById(maliciousInput);
+
+        // Should return null, not execute injection
+        assertNull(result);
+
+        // Verify table still exists
+        assertTrue(userTableExists());
+    }`,
      },
    },
    {
      id: 'action-4',
      type: 'command',
      target: 'mvn test -Dtest=UserControllerTest',
      description: 'Run unit tests to verify fix',
      risk: 'low',
      status: 'pending',
    },
  ],

  // Artifacts
  artifacts: {
    taskPlan: {
      id: 'artifact-1',
      type: 'task_plan',
      title: 'SQL Injection Fix - Task Plan',
      createdAt: '2024-12-08T10:30:00Z',
      content: {
        objective: 'Remediate SQL injection vulnerability CVE-2024-1234 in UserController',
        scope: ['src/controllers/UserController.java', 'src/tests/UserControllerTest.java'],
        approach: 'Replace string concatenation with parameterized queries',
        estimatedDuration: '15 minutes',
        dependencies: ['Database access', 'Test framework'],
      },
    },
    implementationPlan: {
      id: 'artifact-2',
      type: 'implementation_plan',
      title: 'Technical Implementation Plan',
      createdAt: '2024-12-08T10:30:10Z',
      content: {
        steps: [
          'Identify all SQL query construction points',
          'Replace String concatenation with PreparedStatement',
          'Add input validation as defense-in-depth',
          'Create regression tests',
          'Run existing test suite',
        ],
        technicalDetails: 'Using java.sql.PreparedStatement for parameterized queries',
        rollbackPlan: 'Revert to previous commit if tests fail',
      },
    },
    reasoningDoc: {
      id: 'artifact-3',
      type: 'reasoning',
      title: 'Decision Rationale',
      createdAt: '2024-12-08T10:30:20Z',
      content: {
        decision: 'Use PreparedStatement instead of other alternatives',
        alternatives: [
          { option: 'Input sanitization only', rejected: 'Not sufficient for SQL injection' },
          { option: 'ORM migration', rejected: 'Too large scope for this fix' },
          { option: 'Stored procedures', rejected: 'Requires database changes' },
        ],
        justification: 'PreparedStatement provides robust protection while maintaining code simplicity',
      },
    },
  },

  // Feedback history
  feedbackHistory: [
    {
      id: 'feedback-1',
      timestamp: '2024-12-07T14:30:00Z',
      author: 'reviewer@aenealabs.com',
      type: 'suggestion',
      content: 'Consider adding input length validation as defense-in-depth',
      status: 'incorporated',
      response: 'Added input length check before query execution',
    },
    {
      id: 'feedback-2',
      timestamp: '2024-12-06T09:15:00Z',
      author: 'security@aenealabs.com',
      type: 'approval',
      content: 'Approach looks good. PreparedStatement is the correct pattern.',
      status: 'acknowledged',
    },
  ],
};

const MOCK_LIVE_LOGS = [
  { timestamp: '10:30:05', level: 'info', message: 'Starting vulnerability analysis...' },
  { timestamp: '10:30:08', level: 'info', message: 'Loaded context from GraphRAG: 12 relevant code entities' },
  { timestamp: '10:30:12', level: 'info', message: 'Identified 2 vulnerable code locations' },
  { timestamp: '10:30:15', level: 'warning', message: 'High-risk SQL injection pattern detected in getUserById()' },
  { timestamp: '10:30:18', level: 'info', message: 'Generating fix using parameterized query pattern' },
  { timestamp: '10:30:22', level: 'info', message: 'Fix generated. Preparing diff preview...' },
  { timestamp: '10:30:25', level: 'success', message: 'Pre-flight checklist ready. Awaiting approval.' },
];

// Mock data for multiple active agents
const MOCK_ACTIVE_AGENTS = [
  {
    id: 'agent-001',
    name: 'Coder Agent Alpha',
    type: 'coder',
    status: 'awaiting_approval',
    taskSummary: 'Fix SQL injection vulnerability',
    avatar: 'CA',
    avatarColor: 'aura',
  },
  {
    id: 'agent-002',
    name: 'Security Reviewer Beta',
    type: 'reviewer',
    status: 'executing',
    taskSummary: 'Security audit of payment module',
    avatar: 'SR',
    avatarColor: 'olive',
  },
  {
    id: 'agent-003',
    name: 'Validator Agent Gamma',
    type: 'validator',
    status: 'thinking',
    taskSummary: 'Validating authentication changes',
    avatar: 'VA',
    avatarColor: 'warning',
  },
];

// Map of sessions by agent ID for dynamic loading
const MOCK_AGENT_SESSIONS = {
  'agent-001': MOCK_AGENT_SESSION,
  'agent-002': {
    ...MOCK_AGENT_SESSION,
    id: 'session-002',
    agentName: 'Security Reviewer Beta',
    agentType: 'reviewer',
    taskDescription: 'Security audit of payment module PaymentProcessor.java',
    status: 'executing',
    startedAt: '2024-12-08T09:15:00Z',
    thoughtProcess: [
      {
        id: 'thought-sr-1',
        type: 'analysis',
        content: 'Beginning security audit of payment processing module...',
        timestamp: '2024-12-08T09:15:05Z',
      },
      {
        id: 'thought-sr-2',
        type: 'planning',
        content: 'Checking for PCI-DSS compliance issues and secure handling of card data.',
        timestamp: '2024-12-08T09:15:15Z',
      },
      {
        id: 'thought-sr-3',
        type: 'risk_assessment',
        content: 'Identified 3 potential security concerns: unencrypted logging, weak input validation, missing rate limiting.',
        timestamp: '2024-12-08T09:15:25Z',
      },
    ],
    plannedActions: [
      {
        id: 'action-sr-1',
        type: 'file_read',
        target: 'src/payments/PaymentProcessor.java',
        description: 'Analyze payment processing implementation',
        risk: 'low',
        status: 'completed',
      },
      {
        id: 'action-sr-2',
        type: 'security_scan',
        target: 'src/payments/',
        description: 'Run SAST scan on payment module',
        risk: 'low',
        status: 'executing',
      },
    ],
    feedbackHistory: [],
  },
  'agent-003': {
    ...MOCK_AGENT_SESSION,
    id: 'session-003',
    agentName: 'Validator Agent Gamma',
    agentType: 'validator',
    taskDescription: 'Validating authentication changes in AuthService.java',
    status: 'thinking',
    startedAt: '2024-12-08T11:45:00Z',
    thoughtProcess: [
      {
        id: 'thought-va-1',
        type: 'analysis',
        content: 'Reviewing proposed changes to authentication flow...',
        timestamp: '2024-12-08T11:45:05Z',
      },
      {
        id: 'thought-va-2',
        type: 'planning',
        content: 'Will validate OAuth2 token handling and session management changes.',
        timestamp: '2024-12-08T11:45:15Z',
      },
    ],
    plannedActions: [
      {
        id: 'action-va-1',
        type: 'test_run',
        target: 'src/tests/AuthServiceTest.java',
        description: 'Execute authentication test suite',
        risk: 'low',
        status: 'pending',
      },
    ],
    feedbackHistory: [],
  },
};

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

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

function getActionColorClasses(color) {
  const colorMap = {
    olive: { bg: 'bg-olive-100 dark:bg-olive-900/30', icon: 'text-olive-500' },
    aura: { bg: 'bg-aura-100 dark:bg-aura-900/30', icon: 'text-aura-500' },
    warning: { bg: 'bg-warning-100 dark:bg-warning-900/30', icon: 'text-warning-500' },
    critical: { bg: 'bg-critical-100 dark:bg-critical-900/30', icon: 'text-critical-500' },
  };
  return colorMap[color] || colorMap.aura;
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

/**
 * ThoughtBubble - Displays a single thought in the reasoning chain
 */
function ThoughtBubble({ thought, isLast }) {
  const typeConfig = {
    analysis: { icon: MagnifyingGlassIcon, color: 'aura', label: 'Analysis' },
    planning: { icon: ListBulletIcon, color: 'olive', label: 'Planning' },
    decision: { icon: LightBulbIcon, color: 'warning', label: 'Decision' },
    risk_assessment: { icon: ShieldExclamationIcon, color: 'critical', label: 'Risk Assessment' },
  };

  const config = typeConfig[thought.type] || typeConfig.analysis;
  const colors = getActionColorClasses(config.color);
  const Icon = config.icon;

  return (
    <div className="relative flex gap-4">
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-4 top-10 bottom-0 w-px bg-surface-200 dark:bg-surface-700" />
      )}

      {/* Icon */}
      <div className={`relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${colors.bg}`}>
        <Icon className={`w-4 h-4 ${colors.icon}`} />
      </div>

      {/* Content */}
      <div className="flex-1 pb-6">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
            {config.label}
          </span>
          <span className="text-xs text-surface-400 dark:text-surface-500">
            {formatRelativeTime(thought.timestamp)}
          </span>
        </div>
        <p className="text-sm text-surface-700 dark:text-surface-300 leading-relaxed">
          {thought.content}
        </p>
      </div>
    </div>
  );
}

/**
 * ActionCard - Displays a planned action with risk assessment
 */
function ActionCard({ action, onApprove, onReject, onModify }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const actionType = ACTION_TYPES[action.type] || ACTION_TYPES.file_read;
  const risk = RISK_LEVELS[action.risk] || RISK_LEVELS.low;
  const status = EXECUTION_STATUS[action.status] || EXECUTION_STATUS.pending;
  const ActionIcon = actionType.icon;
  const colors = getActionColorClasses(actionType.color);

  return (
    <div className={`
      rounded-xl border-2 transition-all duration-200 overflow-hidden bg-white dark:bg-surface-800
      ${action.status === 'pending' ? risk.border : 'border-surface-200 dark:border-surface-700'}
      ${action.status === 'completed' ? 'opacity-75' : ''}
    `}>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-surface-50 dark:hover:bg-surface-700 transition-colors"
      >
        {/* Action Type Icon */}
        <div className={`p-2 rounded-lg ${colors.bg}`}>
          <ActionIcon className={`w-5 h-5 ${colors.icon}`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
              {actionType.label}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${risk.badge}`}>
              {risk.label}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${status.badge}`}>
              {status.label}
            </span>
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400 truncate font-mono">
            {action.target}
          </p>
        </div>

        {/* Expand icon */}
        <ChevronRightIcon className={`w-5 h-5 text-surface-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-surface-200 dark:border-surface-700">
          {/* Description */}
          <div className="p-4 bg-surface-50 dark:bg-surface-700">
            <p className="text-sm text-surface-600 dark:text-surface-400">
              {action.description}
            </p>
          </div>

          {/* Diff Preview (if applicable) */}
          {action.diff && (
            <div className="border-t border-surface-200 dark:border-surface-700">
              <div className="px-4 py-2 bg-surface-100 dark:bg-surface-800 flex items-center justify-between">
                <span className="text-xs font-medium text-surface-500 dark:text-surface-400">
                  Code Changes
                </span>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-olive-600 dark:text-olive-400">+{action.diff.additions}</span>
                  <span className="text-critical-600 dark:text-critical-400">-{action.diff.deletions}</span>
                </div>
              </div>
              <pre className="p-4 bg-surface-900 dark:bg-surface-950 text-surface-100 text-xs font-mono overflow-x-auto">
                {action.diff.preview}
              </pre>
            </div>
          )}

          {/* Action Buttons (only for pending actions) */}
          {action.status === 'pending' && (
            <div className="p-4 bg-surface-50 dark:bg-surface-700 flex gap-2 border-t border-surface-200 dark:border-surface-700">
              <button
                onClick={() => onReject(action.id)}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-critical-600 dark:text-critical-400 border border-critical-300 dark:border-critical-700 rounded-lg hover:bg-critical-50 dark:hover:bg-critical-900/20 transition-colors"
              >
                <XMarkIcon className="w-4 h-4" />
                Skip
              </button>
              <button
                onClick={() => onModify(action.id)}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-orange-500 hover:bg-orange-600 rounded-lg transition-colors"
              >
                <PencilSquareIcon className="w-4 h-4" />
                Modify
              </button>
              <button
                onClick={() => onApprove(action.id)}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-olive-500 rounded-lg hover:bg-olive-600 transition-colors"
              >
                <CheckIcon className="w-4 h-4" />
                Approve
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * LiveLogEntry - Single log line in the mission control
 */
function LiveLogEntry({ log }) {
  const levelConfig = {
    info: { icon: InformationCircleIcon, color: 'text-aura-500', bg: 'bg-aura-500' },
    warning: { icon: ExclamationTriangleIcon, color: 'text-warning-500', bg: 'bg-warning-500' },
    error: { icon: XCircleIcon, color: 'text-critical-500', bg: 'bg-critical-500' },
    success: { icon: CheckCircleIcon, color: 'text-olive-500', bg: 'bg-olive-500' },
  };

  const config = levelConfig[log.level] || levelConfig.info;
  const Icon = config.icon;

  return (
    <div className="flex items-start gap-3 py-2 px-3 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors font-mono text-xs">
      <span className="text-surface-400 dark:text-surface-500 w-16 flex-shrink-0">
        {log.timestamp}
      </span>
      <Icon className={`w-4 h-4 flex-shrink-0 ${config.color}`} />
      <span className="text-surface-700 dark:text-surface-300 flex-1">
        {log.message}
      </span>
    </div>
  );
}

/**
 * ArtifactCard - Displays a structured artifact
 */
function ArtifactCard({ artifact, onFeedback }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [showFeedbackInput, setShowFeedbackInput] = useState(false);

  const typeConfig = {
    task_plan: { icon: ListBulletIcon, color: 'aura', label: 'Task Plan' },
    implementation_plan: { icon: CodeBracketIcon, color: 'olive', label: 'Implementation Plan' },
    reasoning: { icon: LightBulbIcon, color: 'warning', label: 'Reasoning' },
    walkthrough: { icon: DocumentTextIcon, color: 'aura', label: 'Walkthrough' },
    audit_trail: { icon: ClockIcon, color: 'surface', label: 'Audit Trail' },
  };

  const config = typeConfig[artifact.type] || typeConfig.task_plan;
  const colors = getActionColorClasses(config.color);
  const Icon = config.icon;

  const handleSubmitFeedback = () => {
    if (feedbackText.trim()) {
      onFeedback(artifact.id, feedbackText);
      setFeedbackText('');
      setShowFeedbackInput(false);
    }
  };

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors"
      >
        <div className={`p-2 rounded-lg ${colors.bg}`}>
          <Icon className={`w-5 h-5 ${colors.icon}`} />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-surface-900 dark:text-surface-100">
            {artifact.title}
          </h4>
          <p className="text-xs text-surface-500 dark:text-surface-400">
            {config.label} - {formatRelativeTime(artifact.createdAt)}
          </p>
        </div>
        <ChevronRightIcon className={`w-5 h-5 text-surface-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="border-t border-surface-200 dark:border-surface-700">
          <div className="p-4 bg-surface-50 dark:bg-surface-800/30">
            {/* Render content based on type */}
            {artifact.type === 'task_plan' && (
              <div className="space-y-3">
                <div>
                  <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">Objective</span>
                  <p className="text-sm text-surface-700 dark:text-surface-300 mt-1">{artifact.content.objective}</p>
                </div>
                <div>
                  <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">Scope</span>
                  <ul className="mt-1 space-y-1">
                    {artifact.content.scope.map((item, i) => (
                      <li key={i} className="text-xs font-mono text-surface-600 dark:text-surface-400 flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-aura-500" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">Approach</span>
                  <p className="text-sm text-surface-700 dark:text-surface-300 mt-1">{artifact.content.approach}</p>
                </div>
              </div>
            )}

            {artifact.type === 'implementation_plan' && (
              <div className="space-y-3">
                <div>
                  <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">Steps</span>
                  <ol className="mt-1 space-y-2">
                    {artifact.content.steps.map((step, i) => (
                      <li key={i} className="text-sm text-surface-700 dark:text-surface-300 flex items-start gap-2">
                        <span className="w-5 h-5 rounded-full bg-olive-100 dark:bg-olive-900/30 text-olive-600 dark:text-olive-400 text-xs flex items-center justify-center flex-shrink-0 font-medium">
                          {i + 1}
                        </span>
                        {step}
                      </li>
                    ))}
                  </ol>
                </div>
                <div>
                  <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">Technical Details</span>
                  <p className="text-sm text-surface-600 dark:text-surface-400 mt-1 font-mono">{artifact.content.technicalDetails}</p>
                </div>
              </div>
            )}

            {artifact.type === 'reasoning' && (
              <div className="space-y-3">
                <div>
                  <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">Decision</span>
                  <p className="text-sm text-surface-700 dark:text-surface-300 mt-1">{artifact.content.decision}</p>
                </div>
                <div>
                  <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">Alternatives Considered</span>
                  <div className="mt-2 space-y-2">
                    {artifact.content.alternatives.map((alt, i) => (
                      <div key={i} className="flex items-start gap-2 p-2 bg-critical-50 dark:bg-critical-900/10 rounded-lg">
                        <XCircleIcon className="w-4 h-4 text-critical-500 flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-medium text-surface-700 dark:text-surface-300">{alt.option}</p>
                          <p className="text-xs text-surface-500 dark:text-surface-400">{alt.rejected}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">Justification</span>
                  <p className="text-sm text-surface-700 dark:text-surface-300 mt-1">{artifact.content.justification}</p>
                </div>
              </div>
            )}
          </div>

          {/* Feedback Section */}
          <div className="p-4 border-t border-surface-200 dark:border-surface-700">
            {!showFeedbackInput ? (
              <button
                onClick={() => setShowFeedbackInput(true)}
                className="flex items-center gap-2 text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 transition-colors"
              >
                <ChatBubbleLeftRightIcon className="w-4 h-4" />
                Add Feedback
              </button>
            ) : (
              <div className="space-y-3">
                <textarea
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                  placeholder="Enter your feedback..."
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none"
                />
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => setShowFeedbackInput(false)}
                    className="px-3 py-1.5 text-sm text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSubmitFeedback}
                    disabled={!feedbackText.trim()}
                    className="px-3 py-1.5 text-sm font-medium text-white bg-aura-500 rounded-lg hover:bg-aura-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Submit
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * FeedbackHistoryItem - Single feedback entry
 */
function FeedbackHistoryItem({ feedback }) {
  const typeConfig = {
    suggestion: { icon: LightBulbIcon, color: 'warning', label: 'Suggestion' },
    approval: { icon: CheckCircleIcon, color: 'olive', label: 'Approval' },
    rejection: { icon: XCircleIcon, color: 'critical', label: 'Rejection' },
    question: { icon: ChatBubbleOvalLeftEllipsisIcon, color: 'aura', label: 'Question' },
  };

  const config = typeConfig[feedback.type] || typeConfig.suggestion;
  const colors = getActionColorClasses(config.color);
  const Icon = config.icon;

  const statusStyles = {
    incorporated: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    acknowledged: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    pending: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
  };

  return (
    <div className="flex gap-4 p-4 bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700">
      <div className={`p-2 rounded-lg ${colors.bg} h-fit`}>
        <Icon className={`w-4 h-4 ${colors.icon}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
            {config.label}
          </span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusStyles[feedback.status]}`}>
            {feedback.status}
          </span>
          <span className="text-xs text-surface-400 dark:text-surface-500">
            {formatRelativeTime(feedback.timestamp)}
          </span>
        </div>
        <p className="text-sm text-surface-600 dark:text-surface-400 mb-2">
          {feedback.content}
        </p>
        {feedback.response && (
          <div className="mt-2 pl-3 border-l-2 border-olive-300 dark:border-olive-700">
            <p className="text-xs text-olive-600 dark:text-olive-400">
              Response: {feedback.response}
            </p>
          </div>
        )}
        <p className="text-xs text-surface-400 dark:text-surface-500 mt-2">
          by {feedback.author}
        </p>
      </div>
    </div>
  );
}

/**
 * AgentSelector - Dropdown to select active agents
 */
function AgentSelector({ agents, selectedAgentId, onSelectAgent }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedAgent = agents.find(a => a.id === selectedAgentId) || agents[0];

  const avatarColors = {
    aura: 'bg-aura-500 text-white',
    olive: 'bg-olive-500 text-white',
    warning: 'bg-warning-500 text-white',
    critical: 'bg-critical-500 text-white',
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Selector Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:bg-surface-50 dark:hover:bg-surface-700 transition-colors"
      >
        {/* Selected Agent Avatar */}
        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${avatarColors[selectedAgent?.avatarColor || 'aura']}`}>
          {selectedAgent?.avatar || 'A'}
        </div>

        {/* Selected Agent Info */}
        <div className="text-left">
          <div className="text-sm font-medium text-surface-900 dark:text-surface-100">
            {selectedAgent?.name || 'Select Agent'}
          </div>
          <div className="text-xs text-surface-500 dark:text-surface-400">
            {agents.length} active agent{agents.length !== 1 ? 's' : ''}
          </div>
        </div>

        {/* Dropdown Arrow */}
        <ChevronDownIcon className={`w-4 h-4 text-surface-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] shadow-xl z-50 overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
            <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300">
              Active Agents
            </h4>
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
              Select an agent to view their mission
            </p>
          </div>

          {/* Agent List */}
          <div className="max-h-[300px] overflow-y-auto py-2">
            {agents.map((agent) => {
              const status = EXECUTION_STATUS[agent.status] || EXECUTION_STATUS.pending;
              const isSelected = agent.id === selectedAgentId;

              return (
                <button
                  key={agent.id}
                  onClick={() => {
                    onSelectAgent(agent.id);
                    setIsOpen(false);
                  }}
                  className={`
                    w-full flex items-center gap-3 px-4 py-3 text-left transition-colors
                    ${isSelected
                      ? 'bg-aura-50 dark:bg-aura-900/20'
                      : 'hover:bg-surface-50 dark:hover:bg-surface-700/50'
                    }
                  `}
                >
                  {/* Avatar */}
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${avatarColors[agent.avatarColor]}`}>
                    {agent.avatar}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                        {agent.name}
                      </span>
                      {isSelected && (
                        <CheckIcon className="w-4 h-4 text-aura-500 flex-shrink-0" />
                      )}
                    </div>
                    <div className="text-xs text-surface-500 dark:text-surface-400 truncate">
                      {agent.taskSummary}
                    </div>
                  </div>

                  {/* Status */}
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${status.dot}`} />
                    <span className={`text-xs font-medium ${status.badge} px-2 py-0.5 rounded-full`}>
                      {status.label}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Footer */}
          {agents.length === 0 && (
            <div className="px-4 py-8 text-center">
              <UserCircleIcon className="w-12 h-12 mx-auto text-surface-300 dark:text-surface-600 mb-2" />
              <p className="text-sm text-surface-500 dark:text-surface-400">
                No active agents
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// ACTION MODIFICATION MODAL
// =============================================================================

/**
 * ActionModificationModal - Modal to edit action parameters before execution
 *
 * Allows users to modify:
 * - Target path for file operations
 * - Command arguments for command actions
 * - Description/purpose of the action
 * - Risk level override (with justification)
 */
function ActionModificationModal({ action, isOpen, onClose, onSave }) {
  const [formData, setFormData] = useState({
    target: '',
    description: '',
    risk: 'low',
    riskJustification: '',
    commandArgs: '',
    customDiff: '',
  });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  // Initialize form data when action changes
  useEffect(() => {
    if (action) {
      setFormData({
        target: action.target || '',
        description: action.description || '',
        risk: action.risk || 'low',
        riskJustification: '',
        commandArgs: action.type === 'command' ? action.target : '',
        customDiff: action.diff?.preview || '',
      });
      setErrors({});
    }
  }, [action]);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.target.trim()) {
      newErrors.target = 'Target is required';
    }

    if (!formData.description.trim()) {
      newErrors.description = 'Description is required';
    }

    // If risk was upgraded, require justification
    if (action && formData.risk !== action.risk && !formData.riskJustification.trim()) {
      newErrors.riskJustification = 'Justification required when changing risk level';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }));
    }
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    setSaving(true);
    try {
      const modifiedAction = {
        ...action,
        target: formData.target,
        description: formData.description,
        risk: formData.risk,
        modified: true,
        modifiedAt: new Date().toISOString(),
        modificationNotes: formData.riskJustification || undefined,
      };

      // Update diff if provided
      if (formData.customDiff && action.diff) {
        modifiedAction.diff = {
          ...action.diff,
          preview: formData.customDiff,
        };
      }

      await onSave(modifiedAction);
      onClose();
    } catch (error) {
      setErrors({ submit: error.message || 'Failed to save modifications' });
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen || !action) return null;

  const actionType = ACTION_TYPES[action.type] || ACTION_TYPES.file_read;
  const ActionIcon = actionType.icon;
  const colors = getActionColorClasses(actionType.color);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modify-action-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white dark:bg-surface-800 rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${colors.bg}`}>
                <ActionIcon className={`w-5 h-5 ${colors.icon}`} />
              </div>
              <div>
                <h2
                  id="modify-action-title"
                  className="text-lg font-semibold text-surface-900 dark:text-surface-100"
                >
                  Modify Action
                </h2>
                <p className="text-sm text-surface-500 dark:text-surface-400">
                  {actionType.label} - Customize before execution
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-200 transition-colors rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh] space-y-5">
          {/* Target Path / Command */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              {action.type === 'command' ? 'Command' : 'Target Path'}
            </label>
            <input
              type="text"
              value={formData.target}
              onChange={(e) => handleChange('target', e.target.value)}
              placeholder={action.type === 'command' ? 'npm test --coverage' : 'src/controllers/UserController.java'}
              className={`
                w-full px-3 py-2.5 border rounded-lg bg-white dark:bg-surface-700
                text-surface-900 dark:text-surface-100 placeholder-surface-400
                font-mono text-sm
                focus:ring-2 focus:ring-aura-500 focus:border-transparent
                ${errors.target ? 'border-critical-500' : 'border-surface-300 dark:border-surface-600'}
              `}
            />
            {errors.target && (
              <p className="mt-1 text-xs text-critical-600 dark:text-critical-400">{errors.target}</p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Describe what this action will do..."
              rows={3}
              className={`
                w-full px-3 py-2.5 border rounded-lg bg-white dark:bg-surface-700
                text-surface-900 dark:text-surface-100 placeholder-surface-400 text-sm
                focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none
                ${errors.description ? 'border-critical-500' : 'border-surface-300 dark:border-surface-600'}
              `}
            />
            {errors.description && (
              <p className="mt-1 text-xs text-critical-600 dark:text-critical-400">{errors.description}</p>
            )}
          </div>

          {/* Risk Level */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              Risk Level
            </label>
            <div className="flex gap-3">
              {['low', 'medium', 'high'].map((level) => {
                const riskConfig = RISK_LEVELS[level];
                return (
                  <button
                    key={level}
                    type="button"
                    onClick={() => handleChange('risk', level)}
                    className={`
                      flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all
                      border-2
                      ${formData.risk === level
                        ? `${riskConfig.bg} ${riskConfig.border}`
                        : 'border-surface-200 dark:border-surface-600 bg-surface-50 dark:bg-surface-700 hover:bg-surface-100 dark:hover:bg-surface-600'
                      }
                    `}
                  >
                    <span className={formData.risk === level ? riskConfig.icon : 'text-surface-600 dark:text-surface-400'}>
                      {riskConfig.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Risk Justification (if changed) */}
          {action && formData.risk !== action.risk && (
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
                Justification for Risk Change
              </label>
              <textarea
                value={formData.riskJustification}
                onChange={(e) => handleChange('riskJustification', e.target.value)}
                placeholder="Explain why you're changing the risk level..."
                rows={2}
                className={`
                  w-full px-3 py-2.5 border rounded-lg bg-white dark:bg-surface-700
                  text-surface-900 dark:text-surface-100 placeholder-surface-400 text-sm
                  focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none
                  ${errors.riskJustification ? 'border-critical-500' : 'border-surface-300 dark:border-surface-600'}
                `}
              />
              {errors.riskJustification && (
                <p className="mt-1 text-xs text-critical-600 dark:text-critical-400">{errors.riskJustification}</p>
              )}
            </div>
          )}

          {/* Custom Diff (for file operations) */}
          {action.diff && (
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
                Code Changes (Diff Preview)
              </label>
              <textarea
                value={formData.customDiff}
                onChange={(e) => handleChange('customDiff', e.target.value)}
                placeholder="Modify the diff preview..."
                rows={8}
                className="w-full px-3 py-2.5 border border-surface-300 dark:border-surface-600 rounded-lg
                  bg-surface-900 dark:bg-surface-950 text-surface-100 font-mono text-xs
                  focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none"
              />
              <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">
                Modify the code changes that will be applied
              </p>
            </div>
          )}

          {/* Submit Error */}
          {errors.submit && (
            <div className="p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
              <p className="text-sm text-critical-700 dark:text-critical-400">{errors.submit}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50 flex justify-between items-center">
          <div className="text-xs text-surface-500 dark:text-surface-400">
            Original: <span className="font-mono">{action.target}</span>
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {saving ? (
                <>
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <CheckIcon className="w-4 h-4" />
                  Save Changes
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

// =============================================================================
// MAIN TAB COMPONENTS
// =============================================================================

/**
 * ManagerView - Pre-flight checklist tab
 */
function ManagerView({
  session,
  onApproveAll,
  onRejectAll,
  onApproveAction,
  onRejectAction,
  onModifyAction,
  // Agent selector props
  agents,
  selectedAgentId,
  onSelectAgent,
}) {
  const pendingActions = session.plannedActions.filter(a => a.status === 'pending');
  const completedActions = session.plannedActions.filter(a => a.status === 'completed');

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Agent Selector Row */}
      <div className="px-6 py-4 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Agent Selector */}
            <AgentSelector
              agents={agents}
              selectedAgentId={selectedAgentId}
              onSelectAgent={onSelectAgent}
            />

            {/* Divider */}
            <div className="w-px h-10 bg-surface-200 dark:bg-surface-700" />

            {/* Current Task Info */}
            <div>
              <p className="text-sm font-medium text-surface-700 dark:text-surface-300">
                {session.taskDescription}
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                Started {formatRelativeTime(session.startedAt)}
              </p>
            </div>
          </div>
          {/* Status Badge */}
          <div className={`
            flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium
            ${EXECUTION_STATUS[session.status]?.badge}
          `}>
            <span className={`w-2 h-2 rounded-full ${EXECUTION_STATUS[session.status]?.dot}`} />
            {EXECUTION_STATUS[session.status]?.label}
          </div>
        </div>
      </div>

      {/* Summary Bar */}
      <div className="px-6 py-4 bg-surface-50 dark:bg-surface-800/50 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="text-sm">
              <span className="text-surface-500 dark:text-surface-400">Pending Actions: </span>
              <span className="font-semibold text-surface-900 dark:text-surface-100">{pendingActions.length}</span>
            </div>
            <div className="text-sm">
              <span className="text-surface-500 dark:text-surface-400">Completed: </span>
              <span className="font-semibold text-olive-600 dark:text-olive-400">{completedActions.length}</span>
            </div>
          </div>
          {pendingActions.length > 0 && (
            <div className="flex gap-2">
              <button
                onClick={onRejectAll}
                className="px-4 py-2 text-sm font-medium text-critical-600 dark:text-critical-400 border border-critical-300 dark:border-critical-700 rounded-lg hover:bg-critical-50 dark:hover:bg-critical-900/20 transition-colors"
              >
                Reject All
              </button>
              <button
                onClick={onApproveAll}
                className="px-4 py-2 text-sm font-medium text-white bg-olive-500 rounded-lg hover:bg-olive-600 transition-colors"
              >
                Approve All
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-2 gap-6">
          {/* Thought Process Column */}
          <div>
            <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
              <CpuChipIcon className="w-5 h-5 text-aura-500" />
              Agent Thinking Process
            </h3>
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-4">
              {session.thoughtProcess.map((thought, index) => (
                <ThoughtBubble
                  key={thought.id}
                  thought={thought}
                  isLast={index === session.thoughtProcess.length - 1}
                />
              ))}
            </div>
          </div>

          {/* Planned Actions Column */}
          <div>
            <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
              <ListBulletIcon className="w-5 h-5 text-olive-500" />
              Planned Actions ({session.plannedActions.length})
            </h3>
            <div className="space-y-3">
              {session.plannedActions.map((action) => (
                <ActionCard
                  key={action.id}
                  action={action}
                  onApprove={onApproveAction}
                  onReject={onRejectAction}
                  onModify={onModifyAction}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * MissionControl - Real-time observation tab
 */
function MissionControl({ session, logs, onPause, onResume, onAbort, isPaused }) {
  const logsEndRef = useRef(null);
  const status = EXECUTION_STATUS[session.status] || EXECUTION_STATUS.pending;
  const _StatusIcon = status.icon;

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Page Header */}
      <header className="p-6 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
              <CommandLineIcon className="w-6 h-6 text-aura-600 dark:text-aura-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                Mission Control
              </h1>
              <p className="text-surface-500 dark:text-surface-400">
                Real-time observation and control of agent execution
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Status Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-100 dark:bg-surface-700 rounded-lg">
              <div className={`w-2 h-2 rounded-full ${status.dot}`} />
              <span className="text-sm font-medium text-surface-700 dark:text-surface-300">{status.label}</span>
            </div>
            {/* Control Buttons */}
            {isPaused ? (
              <button
                onClick={onResume}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-olive-500 rounded-lg hover:bg-olive-600 transition-colors"
              >
                <PlayIcon className="w-4 h-4" />
                Resume
              </button>
            ) : (
              <button
                onClick={onPause}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-orange-500 hover:bg-orange-600 text-white rounded-lg transition-colors"
              >
                <PauseIcon className="w-4 h-4" />
                Pause
              </button>
            )}
            <button
              onClick={onAbort}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-critical-600 dark:text-critical-400 border border-critical-300 dark:border-critical-700 rounded-lg hover:bg-critical-50 dark:hover:bg-critical-900/20 transition-colors"
            >
              <StopIcon className="w-4 h-4" />
              Abort
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Live Thinking Stream */}
        <div className="flex-1 flex flex-col border-r border-surface-200 dark:border-surface-700">
          <div className="px-4 py-3 bg-surface-100 dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
            <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 flex items-center gap-2">
              <EyeIcon className="w-4 h-4" />
              Live Thinking
            </h4>
          </div>
          <div className="flex-1 overflow-y-auto p-4 bg-white dark:bg-surface-800">
            {session.thoughtProcess.map((thought, index) => (
              <ThoughtBubble
                key={thought.id}
                thought={thought}
                isLast={index === session.thoughtProcess.length - 1}
              />
            ))}
            {session.status === 'thinking' && (
              <div className="flex items-center gap-2 text-aura-500 animate-pulse">
                <div className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-aura-500 chat-typing-dot" />
                  <span className="w-2 h-2 rounded-full bg-aura-500 chat-typing-dot" />
                  <span className="w-2 h-2 rounded-full bg-aura-500 chat-typing-dot" />
                </div>
                <span className="text-sm">Thinking...</span>
              </div>
            )}
          </div>
        </div>

        {/* Log Stream */}
        <div className="w-[400px] flex flex-col">
          <div className="px-4 py-3 bg-surface-100 dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
            <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 flex items-center gap-2">
              <CommandLineIcon className="w-4 h-4" />
              Execution Log
            </h4>
            <span className="text-xs text-surface-400 dark:text-surface-500">
              {logs.length} entries
            </span>
          </div>
          <div className="flex-1 overflow-y-auto bg-surface-900 dark:bg-surface-950">
            {logs.map((log, index) => (
              <LiveLogEntry key={index} log={log} />
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * ArtifactsPanel - Structured deliverables tab
 */
function ArtifactsPanel({ artifacts, onFeedback }) {
  const artifactList = Object.values(artifacts);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <DocumentDuplicateIcon className="w-5 h-5 text-aura-500" />
            <span className="font-medium text-surface-900 dark:text-surface-100">
              {artifactList.length} Artifacts Generated
            </span>
          </div>
          <button className="flex items-center gap-2 px-3 py-1.5 text-sm text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors">
            <ArrowsPointingOutIcon className="w-4 h-4" />
            Export All
          </button>
        </div>
      </div>

      {/* Artifacts List */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="space-y-4 max-w-3xl">
          {artifactList.map((artifact) => (
            <ArtifactCard
              key={artifact.id}
              artifact={artifact}
              onFeedback={onFeedback}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * FeedbackPanel - Feedback history and integration tab
 */
function FeedbackPanel({ feedbackHistory, onAddFeedback }) {
  const [newFeedback, setNewFeedback] = useState('');
  const [feedbackType, setFeedbackType] = useState('suggestion');

  const handleSubmit = () => {
    if (newFeedback.trim()) {
      onAddFeedback({
        type: feedbackType,
        content: newFeedback,
      });
      setNewFeedback('');
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header Stats */}
      <div className="px-6 py-4 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <ChatBubbleLeftRightIcon className="w-5 h-5 text-aura-500" />
            <span className="font-medium text-surface-900 dark:text-surface-100">
              Feedback History
            </span>
          </div>
          <div className="flex gap-4 text-sm">
            <span className="text-surface-500 dark:text-surface-400">
              Total: <span className="font-semibold text-surface-900 dark:text-surface-100">{feedbackHistory.length}</span>
            </span>
            <span className="text-surface-500 dark:text-surface-400">
              Incorporated: <span className="font-semibold text-olive-600 dark:text-olive-400">{feedbackHistory.filter(f => f.status === 'incorporated').length}</span>
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Feedback History List */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="space-y-4 max-w-2xl">
            {feedbackHistory.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-surface-400 dark:text-surface-500">
                <ChatBubbleOvalLeftEllipsisIcon className="w-12 h-12 mb-3" />
                <p className="text-lg font-medium">No feedback yet</p>
                <p className="text-sm">Add feedback to help the agent improve</p>
              </div>
            ) : (
              feedbackHistory.map((feedback) => (
                <FeedbackHistoryItem key={feedback.id} feedback={feedback} />
              ))
            )}
          </div>
        </div>

        {/* Add Feedback Panel */}
        <div className="w-[350px] border-l border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 p-6">
          <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-4">
            Add Feedback
          </h4>

          {/* Feedback Type Selector */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Type
            </label>
            <div className="flex gap-2">
              {[
                { value: 'suggestion', label: 'Suggestion', icon: LightBulbIcon },
                { value: 'question', label: 'Question', icon: ChatBubbleOvalLeftEllipsisIcon },
              ].map((type) => (
                <button
                  key={type.value}
                  onClick={() => setFeedbackType(type.value)}
                  className={`
                    flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-lg transition-colors
                    ${feedbackType === type.value
                      ? 'bg-aura-500 text-white'
                      : 'bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-200 dark:hover:bg-surface-600'
                    }
                  `}
                >
                  <type.icon className="w-4 h-4" />
                  {type.label}
                </button>
              ))}
            </div>
          </div>

          {/* Feedback Input */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Message
            </label>
            <textarea
              value={newFeedback}
              onChange={(e) => setNewFeedback(e.target.value)}
              placeholder="Enter your feedback..."
              rows={5}
              className="w-full px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none"
            />
          </div>

          {/* Submit Button */}
          <button
            onClick={handleSubmit}
            disabled={!newFeedback.trim()}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-aura-500 rounded-lg hover:bg-aura-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <PaperAirplaneIcon className="w-4 h-4" />
            Submit Feedback
          </button>

          {/* Help Text */}
          <p className="mt-4 text-xs text-surface-500 dark:text-surface-400">
            Your feedback helps the agent learn and improve. Suggestions are automatically incorporated into future executions.
          </p>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function AgentManagerView() {
  // URL params and navigation
  const { agentId } = useParams();
  const navigate = useNavigate();

  // Toast notifications
  const { toast } = useToast();

  // State
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [session, setSession] = useState(null);
  const [activeTab, setActiveTab] = useState('manager');
  const [logs, setLogs] = useState([]);
  const [isPaused, setIsPaused] = useState(false);
  const [feedbackHistory, setFeedbackHistory] = useState([]);
  const [activeAgents, setActiveAgents] = useState([]);
  const [selectedAgentId, setSelectedAgentId] = useState(agentId || null);
  const [modifyModalOpen, setModifyModalOpen] = useState(false);
  const [actionToModify, setActionToModify] = useState(null);

  // Load mock data on mount only (selectedAgentId captured at initial render)
  useEffect(() => {
    const timer = setTimeout(() => {
      setActiveAgents(MOCK_ACTIVE_AGENTS);
      // Set default selected agent if none specified
      const initialAgentId = selectedAgentId || (MOCK_ACTIVE_AGENTS.length > 0 ? MOCK_ACTIVE_AGENTS[0].id : null);
      if (!selectedAgentId && initialAgentId) {
        setSelectedAgentId(initialAgentId);
      }
      // Load session for the initial agent
      const initialSession = MOCK_AGENT_SESSIONS[initialAgentId] || MOCK_AGENT_SESSION;
      setSession(initialSession);
      setLogs(MOCK_LIVE_LOGS);
      setFeedbackHistory(initialSession.feedbackHistory || []);
      setLoading(false);
    }, 800);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync URL with selected agent
  useEffect(() => {
    if (selectedAgentId && selectedAgentId !== agentId) {
      navigate(`/agents/mission-control/${selectedAgentId}`, { replace: true });
    }
  }, [selectedAgentId, agentId, navigate]);

  // Handle agent selection - load the selected agent's session data
  const handleSelectAgent = (newAgentId) => {
    setSelectedAgentId(newAgentId);
    // Load the session data for the selected agent
    const agentSession = MOCK_AGENT_SESSIONS[newAgentId];
    if (agentSession) {
      setSession(agentSession);
      setFeedbackHistory(agentSession.feedbackHistory || []);
    }
  };

  // Handle refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await new Promise(resolve => setTimeout(resolve, 500));
      // Refresh with the current selected agent's session
      const currentSession = MOCK_AGENT_SESSIONS[selectedAgentId] || MOCK_AGENT_SESSION;
      setSession(currentSession);
      setLogs(MOCK_LIVE_LOGS);
      setFeedbackHistory(currentSession.feedbackHistory || []);
      toast.success('Mission Control refreshed');
    } catch (err) {
      toast.error('Failed to refresh Mission Control');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Action handlers
  const handleApproveAll = () => {
    setSession(prev => ({
      ...prev,
      plannedActions: prev.plannedActions.map(a =>
        a.status === 'pending' ? { ...a, status: 'completed' } : a
      ),
    }));
  };

  const handleRejectAll = () => {
    setSession(prev => ({
      ...prev,
      plannedActions: prev.plannedActions.filter(a => a.status !== 'pending'),
    }));
  };

  const handleApproveAction = (actionId) => {
    setSession(prev => ({
      ...prev,
      plannedActions: prev.plannedActions.map(a =>
        a.id === actionId ? { ...a, status: 'completed' } : a
      ),
    }));
  };

  const handleRejectAction = (actionId) => {
    setSession(prev => ({
      ...prev,
      plannedActions: prev.plannedActions.filter(a => a.id !== actionId),
    }));
  };

  const handleModifyAction = (actionId) => {
    const action = session.plannedActions.find(a => a.id === actionId);
    if (action) {
      setActionToModify(action);
      setModifyModalOpen(true);
    }
  };

  const handleSaveModifiedAction = async (modifiedAction) => {
    // Update the action in the session
    setSession(prev => ({
      ...prev,
      plannedActions: prev.plannedActions.map(a =>
        a.id === modifiedAction.id ? modifiedAction : a
      ),
    }));

    toast.success(`Action "${modifiedAction.description}" modified successfully`, {
      title: 'Action Modified',
    });

    setModifyModalOpen(false);
    setActionToModify(null);
  };

  const handlePause = () => setIsPaused(true);
  const handleResume = () => setIsPaused(false);
  const handleAbort = () => {
    setSession(prev => ({ ...prev, status: 'failed' }));
  };

  const handleArtifactFeedback = (artifactId, feedback) => {
    const newFeedback = {
      id: `feedback-${Date.now()}`,
      timestamp: new Date().toISOString(),
      author: 'current-user@aenealabs.com',
      type: 'suggestion',
      content: feedback,
      status: 'pending',
      artifactId,
    };
    setFeedbackHistory(prev => [newFeedback, ...prev]);
  };

  const handleAddFeedback = ({ type, content }) => {
    const newFeedback = {
      id: `feedback-${Date.now()}`,
      timestamp: new Date().toISOString(),
      author: 'current-user@aenealabs.com',
      type,
      content,
      status: 'pending',
    };
    setFeedbackHistory(prev => [newFeedback, ...prev]);
  };

  if (loading) {
    return <PageSkeleton />;
  }

  const tabs = [
    { id: 'manager', label: 'Manager View', icon: EyeIcon },
    { id: 'live', label: 'Live Execution', icon: SignalIcon },
    { id: 'mission', label: 'Mission Control', icon: CommandLineIcon },
    { id: 'artifacts', label: 'Artifacts', icon: DocumentDuplicateIcon },
    { id: 'feedback', label: 'Feedback', icon: ChatBubbleLeftRightIcon },
  ];

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="px-6 py-4 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        {/* Row 1: Page Title, Description, and Refresh Button */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              Mission Control
            </h1>
            <p className="text-surface-500 dark:text-surface-400 mt-1">
              Real-time observation and control of agent execution
            </p>
          </div>
          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <ArrowPathIcon className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Row 2: Tab Navigation */}
        <nav className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors
                ${activeTab === tab.id
                  ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400'
                  : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'
                }
              `}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'manager' && (
          <ManagerView
            session={session}
            onApproveAll={handleApproveAll}
            onRejectAll={handleRejectAll}
            onApproveAction={handleApproveAction}
            onRejectAction={handleRejectAction}
            onModifyAction={handleModifyAction}
            agents={activeAgents}
            selectedAgentId={selectedAgentId}
            onSelectAgent={handleSelectAgent}
          />
        )}
        {activeTab === 'live' && (
          <RealTimeExecutionPanel
            executionId={session.id}
            onClose={() => setActiveTab('manager')}
          />
        )}
        {activeTab === 'mission' && (
          <MissionControl
            session={session}
            logs={logs}
            onPause={handlePause}
            onResume={handleResume}
            onAbort={handleAbort}
            isPaused={isPaused}
          />
        )}
        {activeTab === 'artifacts' && (
          <ArtifactsPanel
            artifacts={session.artifacts}
            onFeedback={handleArtifactFeedback}
          />
        )}
        {activeTab === 'feedback' && (
          <FeedbackPanel
            feedbackHistory={feedbackHistory}
            onAddFeedback={handleAddFeedback}
          />
        )}
      </div>

      {/* Action Modification Modal */}
      <ActionModificationModal
        action={actionToModify}
        isOpen={modifyModalOpen}
        onClose={() => {
          setModifyModalOpen(false);
          setActionToModify(null);
        }}
        onSave={handleSaveModifiedAction}
      />
    </div>
  );
}
