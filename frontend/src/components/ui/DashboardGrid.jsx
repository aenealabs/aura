import { useState, useEffect } from 'react';
import {
  GridLayout,
  useContainerWidth,
  useResponsiveLayout,
  verticalCompactor,
} from 'react-grid-layout';
import {
  Cog6ToothIcon,
  CheckIcon,
  XMarkIcon,
  ArrowPathIcon,
  PlusIcon,
  CpuChipIcon,
  ClockIcon,
  BugAntIcon,
  ShieldCheckIcon,
  BeakerIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  ChartPieIcon,
  ListBulletIcon,
  ServerStackIcon,
  HeartIcon,
  BoltIcon,
  FunnelIcon,
  BellAlertIcon,
  ShareIcon,
  // New ADR-064 widget icons
  ArrowTrendingUpIcon,
  Square3Stack3DIcon,
  CurrencyDollarIcon,
  CodeBracketIcon,
  RocketLaunchIcon,
  ClipboardDocumentCheckIcon,
  ScaleIcon,
  TableCellsIcon,
} from '@heroicons/react/24/outline';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

// Breakpoint and column configuration
const BREAKPOINTS = { lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 };
const COLS = { lg: 12, md: 8, sm: 4, xs: 4, xxs: 2 };

// Storage key for localStorage (v3 = compact metric cards with h:3)
const LAYOUT_STORAGE_KEY = 'aura_dashboard_layout_v3';

// Default layouts for different breakpoints
// Grid uses 12-column layout for finer resize control (40px row height)
const DEFAULT_LAYOUTS = {
  lg: [
    { i: 'active-agents', x: 0, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'pending-approvals', x: 2, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'vulnerabilities', x: 4, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'patches-deployed', x: 6, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'sandbox-tests', x: 8, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'anomalies', x: 10, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'vulnerability-trend', x: 0, y: 3, w: 6, h: 7, minW: 3, minH: 5 },
    { i: 'severity-distribution', x: 6, y: 3, w: 6, h: 7, minW: 3, minH: 5 },
    { i: 'security-alerts', x: 0, y: 10, w: 4, h: 7, minW: 3, minH: 5 },
    { i: 'activity-feed', x: 4, y: 10, w: 4, h: 8, minW: 3, minH: 5 },
    { i: 'agent-status', x: 8, y: 10, w: 4, h: 6, minW: 3, minH: 4 },
    { i: 'system-health', x: 8, y: 16, w: 4, h: 4, minW: 3, minH: 4 },
  ],
  md: [
    { i: 'active-agents', x: 0, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'pending-approvals', x: 2, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'vulnerabilities', x: 4, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'patches-deployed', x: 6, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'sandbox-tests', x: 0, y: 3, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'anomalies', x: 2, y: 3, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'vulnerability-trend', x: 0, y: 6, w: 4, h: 7, minW: 3, minH: 5 },
    { i: 'severity-distribution', x: 4, y: 6, w: 4, h: 7, minW: 3, minH: 5 },
    { i: 'security-alerts', x: 0, y: 13, w: 4, h: 7, minW: 3, minH: 5 },
    { i: 'activity-feed', x: 4, y: 13, w: 4, h: 8, minW: 3, minH: 5 },
    { i: 'agent-status', x: 0, y: 21, w: 4, h: 6, minW: 3, minH: 4 },
    { i: 'system-health', x: 4, y: 21, w: 4, h: 6, minW: 3, minH: 4 },
  ],
  sm: [
    { i: 'active-agents', x: 0, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'pending-approvals', x: 2, y: 0, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'vulnerabilities', x: 0, y: 3, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'patches-deployed', x: 2, y: 3, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'sandbox-tests', x: 0, y: 6, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'anomalies', x: 2, y: 6, w: 2, h: 3, minW: 2, minH: 3 },
    { i: 'vulnerability-trend', x: 0, y: 9, w: 4, h: 7, minW: 3, minH: 5 },
    { i: 'severity-distribution', x: 0, y: 16, w: 4, h: 7, minW: 3, minH: 5 },
    { i: 'security-alerts', x: 0, y: 23, w: 4, h: 7, minW: 3, minH: 5 },
    { i: 'activity-feed', x: 0, y: 30, w: 4, h: 8, minW: 3, minH: 5 },
    { i: 'agent-status', x: 0, y: 38, w: 4, h: 6, minW: 3, minH: 4 },
    { i: 'system-health', x: 0, y: 44, w: 4, h: 6, minW: 3, minH: 4 },
  ],
};

// Widget registry with all available widgets
export const WIDGET_REGISTRY = {
  'active-agents': {
    id: 'active-agents',
    title: 'Active Agents',
    category: 'metrics',
    size: 'small',
    icon: CpuChipIcon,
    description: 'Monitor running AI agents',
    color: 'aura',
  },
  'pending-approvals': {
    id: 'pending-approvals',
    title: 'Pending Approvals',
    category: 'metrics',
    size: 'small',
    icon: ClockIcon,
    description: 'Track HITL approval queue',
    color: 'warning',
  },
  'vulnerabilities': {
    id: 'vulnerabilities',
    title: 'Open Vulnerabilities',
    category: 'metrics',
    size: 'small',
    icon: BugAntIcon,
    description: 'Active security issues',
    color: 'critical',
  },
  'patches-deployed': {
    id: 'patches-deployed',
    title: 'Patches Deployed',
    category: 'metrics',
    size: 'small',
    icon: ShieldCheckIcon,
    description: 'Successfully deployed patches',
    color: 'olive',
  },
  'sandbox-tests': {
    id: 'sandbox-tests',
    title: 'Sandbox Tests',
    category: 'metrics',
    size: 'small',
    icon: BeakerIcon,
    description: 'Running sandbox validations',
    color: 'aura',
  },
  'anomalies': {
    id: 'anomalies',
    title: 'Anomalies Detected',
    category: 'metrics',
    size: 'small',
    icon: ExclamationTriangleIcon,
    description: 'Unusual activity alerts',
    color: 'warning',
  },
  'vulnerability-trend': {
    id: 'vulnerability-trend',
    title: 'Vulnerability Trend',
    category: 'charts',
    size: 'medium',
    icon: ChartBarIcon,
    description: '15-day vulnerability history',
    color: 'critical',
  },
  'severity-distribution': {
    id: 'severity-distribution',
    title: 'Severity Distribution',
    category: 'charts',
    size: 'medium',
    icon: ChartPieIcon,
    description: 'Breakdown by severity level',
    color: 'aura',
  },
  'activity-feed': {
    id: 'activity-feed',
    title: 'Activity Feed',
    category: 'feed',
    size: 'large',
    icon: ListBulletIcon,
    description: 'Real-time system activity',
    color: 'surface',
  },
  'agent-status': {
    id: 'agent-status',
    title: 'Agent Status',
    category: 'status',
    size: 'medium',
    icon: ServerStackIcon,
    description: 'Coder, Reviewer, Validator status',
    color: 'aura',
  },
  'system-health': {
    id: 'system-health',
    title: 'System Health',
    category: 'status',
    size: 'medium',
    icon: HeartIcon,
    description: 'API, GraphRAG, LLM health',
    color: 'olive',
  },
  'quick-actions': {
    id: 'quick-actions',
    title: 'Quick Actions',
    category: 'actions',
    size: 'small',
    icon: BoltIcon,
    description: 'Common operations shortcuts',
    color: 'aura',
  },
  'approval-funnel': {
    id: 'approval-funnel',
    title: 'Approval Funnel',
    category: 'charts',
    size: 'medium',
    icon: FunnelIcon,
    description: 'Detection to deployment pipeline',
    color: 'aura',
  },
  'security-alerts': {
    id: 'security-alerts',
    title: 'Security Alerts',
    category: 'security',
    size: 'medium',
    icon: BellAlertIcon,
    description: 'Critical and high priority security alerts',
    color: 'critical',
  },
  'graph-metrics': {
    id: 'graph-metrics',
    title: 'Graph Metrics',
    category: 'status',
    size: 'small',
    icon: ShareIcon,
    description: 'Knowledge Graph nodes, edges, and query stats',
    color: 'aura',
  },
  // =====================================================================
  // New ADR-064 Widgets
  // =====================================================================
  'mttr': {
    id: 'mttr',
    title: 'Mean Time to Remediate',
    category: 'metrics',
    size: 'small',
    icon: ClockIcon,
    description: 'Average time to fix vulnerabilities (in hours)',
    color: 'aura',
  },
  'cve-trend': {
    id: 'cve-trend',
    title: 'CVE Trend',
    category: 'charts',
    size: 'medium',
    icon: ChartBarIcon,
    description: '30-day trend of CVE discoveries and patches',
    color: 'critical',
  },
  'agent-health-grid': {
    id: 'agent-health-grid',
    title: 'Agent Health Grid',
    category: 'status',
    size: 'medium',
    icon: Square3Stack3DIcon,
    description: 'Health status of all active agents',
    color: 'aura',
  },
  'sandbox-utilization': {
    id: 'sandbox-utilization',
    title: 'Sandbox Utilization',
    category: 'metrics',
    size: 'small',
    icon: BeakerIcon,
    description: 'Current sandbox environment utilization percentage',
    color: 'aura',
  },
  'environment-status': {
    id: 'environment-status',
    title: 'Environment Status',
    category: 'status',
    size: 'small',
    icon: ServerStackIcon,
    description: 'Status of dev/qa/prod environments',
    color: 'olive',
  },
  'gpu-jobs-queued': {
    id: 'gpu-jobs-queued',
    title: 'GPU Jobs Queued',
    category: 'metrics',
    size: 'small',
    icon: CpuChipIcon,
    description: 'Number of GPU jobs waiting in queue',
    color: 'warning',
  },
  'deployment-velocity': {
    id: 'deployment-velocity',
    title: 'Deployment Velocity',
    category: 'metrics',
    size: 'small',
    icon: RocketLaunchIcon,
    description: 'Deployments per day (7-day average)',
    color: 'olive',
  },
  'code-quality-score': {
    id: 'code-quality-score',
    title: 'Code Quality Score',
    category: 'metrics',
    size: 'small',
    icon: CodeBracketIcon,
    description: 'Overall code quality score (0-100)',
    color: 'aura',
  },
  'test-coverage-trend': {
    id: 'test-coverage-trend',
    title: 'Test Coverage Trend',
    category: 'charts',
    size: 'medium',
    icon: ChartBarIcon,
    description: 'Test coverage percentage over time',
    color: 'olive',
  },
  'pr-velocity': {
    id: 'pr-velocity',
    title: 'PR Velocity by Team',
    category: 'charts',
    size: 'medium',
    icon: ChartBarIcon,
    description: 'Pull request velocity grouped by team',
    color: 'aura',
  },
  'compliance-progress': {
    id: 'compliance-progress',
    title: 'Compliance Progress',
    category: 'compliance',
    size: 'small',
    icon: ClipboardDocumentCheckIcon,
    description: 'Overall compliance readiness percentage',
    color: 'aura',
  },
  'risk-posture': {
    id: 'risk-posture',
    title: 'Risk Posture Score',
    category: 'compliance',
    size: 'small',
    icon: ScaleIcon,
    description: 'Composite risk posture score (0-100)',
    color: 'olive',
  },
  'key-incidents': {
    id: 'key-incidents',
    title: 'Key Incidents',
    category: 'compliance',
    size: 'large',
    icon: TableCellsIcon,
    description: 'Recent key security incidents',
    color: 'critical',
  },
  'monthly-cost': {
    id: 'monthly-cost',
    title: 'Monthly Cost',
    category: 'cost',
    size: 'small',
    icon: CurrencyDollarIcon,
    description: 'Current month infrastructure cost',
    color: 'surface',
  },
  'cost-trend': {
    id: 'cost-trend',
    title: 'Cost Trend',
    category: 'cost',
    size: 'medium',
    icon: ArrowTrendingUpIcon,
    description: '30-day infrastructure cost trend',
    color: 'aura',
  },
  // =====================================================================
  // ADR-083: Runtime Agent Security Platform Widgets
  // =====================================================================
  'red-team-block-rate': {
    id: 'red-team-block-rate',
    title: 'Red Team Block Rate',
    category: 'security',
    size: 'small',
    icon: ShieldCheckIcon,
    description: 'Percentage of adversarial attacks blocked by security controls',
    color: 'olive',
  },
  'shadow-agents': {
    id: 'shadow-agents',
    title: 'Shadow Agents Detected',
    category: 'security',
    size: 'small',
    icon: ExclamationTriangleIcon,
    description: 'Unregistered agents discovered via traffic analysis',
    color: 'critical',
  },
  'behavioral-anomalies': {
    id: 'behavioral-anomalies',
    title: 'Behavioral Anomalies',
    category: 'security',
    size: 'medium',
    icon: BellAlertIcon,
    description: 'Recent behavioral deviations detected by baseline engine',
    color: 'warning',
  },
  'correlation-rate': {
    id: 'correlation-rate',
    title: 'Correlation Rate',
    category: 'security',
    size: 'small',
    icon: ShareIcon,
    description: 'Runtime events correlated to source code root causes',
    color: 'aura',
  },
  'red-team-by-category': {
    id: 'red-team-by-category',
    title: 'Red Team Results by Category',
    category: 'charts',
    size: 'medium',
    icon: ChartBarIcon,
    description: 'Attack test outcomes grouped by AURA-ATT&CK category',
    color: 'aura',
  },
  'agent-traffic-volume': {
    id: 'agent-traffic-volume',
    title: 'Agent Traffic Volume',
    category: 'charts',
    size: 'medium',
    icon: ChartBarIcon,
    description: 'Agent traffic events captured over time (24h trend)',
    color: 'aura',
  },
  'agent-traffic-by-type': {
    id: 'agent-traffic-by-type',
    title: 'Agent Traffic by Type',
    category: 'charts',
    size: 'medium',
    icon: ChartPieIcon,
    description: 'Distribution of agent traffic by event type',
    color: 'aura',
  },
  // =====================================================================
  // ADR-084: Native Vulnerability Scanner Widgets
  // =====================================================================
  'scanner-findings-by-severity': {
    id: 'scanner-findings-by-severity',
    title: 'Findings by Severity',
    category: 'security',
    size: 'medium',
    icon: ChartBarIcon,
    description: 'Stacked bar chart of vulnerability findings by severity over 7 days',
    color: 'critical',
  },
  'scanner-active-scans': {
    id: 'scanner-active-scans',
    title: 'Active Scans',
    category: 'metrics',
    size: 'small',
    icon: BoltIcon,
    description: 'Currently running vulnerability scans with pipeline progress',
    color: 'aura',
  },
  'scanner-pipeline-progress': {
    id: 'scanner-pipeline-progress',
    title: 'Scan Pipeline Progress',
    category: 'security',
    size: 'large',
    icon: FunnelIcon,
    description: '7-stage scan pipeline visualization with progress bars',
    color: 'aura',
  },
  'scanner-true-positive-rate': {
    id: 'scanner-true-positive-rate',
    title: 'True Positive Rate',
    category: 'metrics',
    size: 'small',
    icon: ShieldCheckIcon,
    description: 'Animated gauge showing scanner true positive accuracy',
    color: 'olive',
  },
  'scanner-llm-token-spend': {
    id: 'scanner-llm-token-spend',
    title: 'LLM Token Spend',
    category: 'metrics',
    size: 'small',
    icon: CurrencyDollarIcon,
    description: 'Daily and monthly LLM token cost tracking',
    color: 'warning',
  },
  'scanner-alarm-status': {
    id: 'scanner-alarm-status',
    title: 'Scanner Alarm Status',
    category: 'security',
    size: 'small',
    icon: BellAlertIcon,
    description: 'Scanner health alarm grid with OK/WARNING/ALARM states',
    color: 'critical',
  },
  'scanner-recent-activity': {
    id: 'scanner-recent-activity',
    title: 'Recent Scan Activity',
    category: 'security',
    size: 'medium',
    icon: ListBulletIcon,
    description: 'Filterable feed of recent scan completions and findings',
    color: 'aura',
  },
  'scanner-findings-requiring-approval': {
    id: 'scanner-findings-requiring-approval',
    title: 'Findings Requiring Approval',
    category: 'metrics',
    size: 'small',
    icon: ClockIcon,
    description: 'Count of findings awaiting human-in-the-loop approval',
    color: 'warning',
  },
  'scanner-duration-trend': {
    id: 'scanner-duration-trend',
    title: 'Scan Duration Trend',
    category: 'charts',
    size: 'medium',
    icon: ArrowTrendingUpIcon,
    description: 'SVG line chart showing Avg/P50/P95 scan durations over time',
    color: 'aura',
  },
  'scanner-stage-duration': {
    id: 'scanner-stage-duration',
    title: 'Stage Duration Waterfall',
    category: 'charts',
    size: 'medium',
    icon: ChartBarIcon,
    description: 'Horizontal stacked bar showing per-stage scan durations',
    color: 'aura',
  },
  'scanner-findings-by-cwe': {
    id: 'scanner-findings-by-cwe',
    title: 'Findings by CWE',
    category: 'charts',
    size: 'medium',
    icon: ChartBarIcon,
    description: 'Horizontal bar chart of findings grouped by CWE category',
    color: 'critical',
  },
  'scanner-llm-latency': {
    id: 'scanner-llm-latency',
    title: 'LLM Latency',
    category: 'metrics',
    size: 'small',
    icon: BoltIcon,
    description: 'P50/P95/P99 latency percentiles for LLM analysis calls',
    color: 'aura',
  },
  'scanner-concurrent-utilization': {
    id: 'scanner-concurrent-utilization',
    title: 'Concurrent Utilization',
    category: 'metrics',
    size: 'small',
    icon: ServerStackIcon,
    description: 'SVG gauge showing active vs max concurrent scan capacity',
    color: 'aura',
  },
  'scanner-critical-findings-trend': {
    id: 'scanner-critical-findings-trend',
    title: 'Critical Findings Trend',
    category: 'charts',
    size: 'medium',
    icon: ArrowTrendingUpIcon,
    description: '30-day area chart of critical vulnerability finding counts',
    color: 'critical',
  },
  'scanner-queue-depth': {
    id: 'scanner-queue-depth',
    title: 'Scan Queue Depth',
    category: 'metrics',
    size: 'small',
    icon: Square3Stack3DIcon,
    description: 'Number of scans waiting in queue with trend indicator',
    color: 'warning',
  },
  'scanner-candidate-funnel': {
    id: 'scanner-candidate-funnel',
    title: 'Candidate Funnel',
    category: 'charts',
    size: 'medium',
    icon: FunnelIcon,
    description: '4-stage funnel visualization of candidate filtering pipeline',
    color: 'aura',
  },
  'scanner-findings-by-language': {
    id: 'scanner-findings-by-language',
    title: 'Findings by Language',
    category: 'charts',
    size: 'small',
    icon: ChartPieIcon,
    description: 'Donut chart of vulnerability findings by programming language',
    color: 'aura',
  },
  'scanner-verification-status': {
    id: 'scanner-verification-status',
    title: 'Verification Status',
    category: 'charts',
    size: 'small',
    icon: ChartPieIcon,
    description: 'Donut chart of finding verification status distribution',
    color: 'olive',
  },
  'scanner-cleanup-activity': {
    id: 'scanner-cleanup-activity',
    title: 'Cleanup Activity',
    category: 'charts',
    size: 'medium',
    icon: ChartBarIcon,
    description: 'Stacked bar chart of artifact cleanup operations over time',
    color: 'aura',
  },
  'scanner-depth-distribution': {
    id: 'scanner-depth-distribution',
    title: 'Scan Depth Distribution',
    category: 'charts',
    size: 'small',
    icon: ChartPieIcon,
    description: 'Donut chart showing distribution of scan depth levels',
    color: 'aura',
  },
};

// Helper to get saved layout from localStorage
const getSavedLayout = () => {
  try {
    const saved = localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      return {
        layouts: parsed.layouts || DEFAULT_LAYOUTS,
        visibleWidgets: parsed.visibleWidgets || Object.keys(DEFAULT_LAYOUTS.lg.reduce((acc, item) => {
          acc[item.i] = true;
          return acc;
        }, {})),
      };
    }
  } catch (e) {
    console.warn('Failed to load saved layout:', e);
  }
  return {
    layouts: DEFAULT_LAYOUTS,
    visibleWidgets: DEFAULT_LAYOUTS.lg.map(item => item.i),
  };
};

// Helper to save layout to localStorage
const saveLayout = (layouts, visibleWidgets) => {
  try {
    localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify({ layouts, visibleWidgets }));
  } catch (e) {
    console.warn('Failed to save layout:', e);
  }
};

export default function DashboardGrid({ children: _children, renderWidget }) {
  const [isEditMode, setIsEditMode] = useState(false);
  const [layouts, setLayouts] = useState(DEFAULT_LAYOUTS);
  const [visibleWidgets, setVisibleWidgets] = useState([]);
  const [showWidgetPicker, setShowWidgetPicker] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [pendingLayouts, setPendingLayouts] = useState(null);
  const [pendingVisibleWidgets, setPendingVisibleWidgets] = useState(null);

  // Use container width hook for responsive behavior
  const { width, containerRef, mounted } = useContainerWidth({ initialWidth: 1280 });

  // Get current visible widgets and layouts based on mode
  const currentVisibleWidgets = isEditMode ? (pendingVisibleWidgets || visibleWidgets) : visibleWidgets;
  const currentLayouts = isEditMode ? (pendingLayouts || layouts) : layouts;

  // Filter layouts to only include visible widgets
  const filteredLayouts = Object.keys(currentLayouts).reduce((acc, breakpoint) => {
    acc[breakpoint] = currentLayouts[breakpoint].filter(item =>
      currentVisibleWidgets.includes(item.i)
    );
    return acc;
  }, {});

  // Use responsive layout hook
  const { layout, cols, breakpoint } = useResponsiveLayout({
    width,
    breakpoints: BREAKPOINTS,
    cols: COLS,
    layouts: filteredLayouts,
    compactType: 'vertical',
    onLayoutChange: (currentLayout, allLayouts) => {
      if (isEditMode) {
        setPendingLayouts(allLayouts);
        setHasUnsavedChanges(true);
      }
    },
  });

  // Load saved layout on mount
  useEffect(() => {
    const saved = getSavedLayout();
    setLayouts(saved.layouts);
    setVisibleWidgets(saved.visibleWidgets);
  }, []);

  // Enter edit mode
  const enterEditMode = () => {
    setPendingLayouts(layouts);
    setPendingVisibleWidgets([...visibleWidgets]);
    setIsEditMode(true);
    setHasUnsavedChanges(false);
  };

  // Save changes
  const saveChanges = () => {
    const newLayouts = pendingLayouts || layouts;
    const newVisibleWidgets = pendingVisibleWidgets || visibleWidgets;
    setLayouts(newLayouts);
    setVisibleWidgets(newVisibleWidgets);
    saveLayout(newLayouts, newVisibleWidgets);
    setIsEditMode(false);
    setHasUnsavedChanges(false);
    setPendingLayouts(null);
    setPendingVisibleWidgets(null);
  };

  // Cancel changes
  const cancelChanges = () => {
    setIsEditMode(false);
    setHasUnsavedChanges(false);
    setPendingLayouts(null);
    setPendingVisibleWidgets(null);
  };

  // Reset to default
  const resetToDefault = () => {
    setPendingLayouts(DEFAULT_LAYOUTS);
    setPendingVisibleWidgets(DEFAULT_LAYOUTS.lg.map(item => item.i));
    setHasUnsavedChanges(true);
  };

  // Remove widget
  const removeWidget = (widgetId) => {
    const newVisibleWidgets = (pendingVisibleWidgets || visibleWidgets).filter(id => id !== widgetId);
    setPendingVisibleWidgets(newVisibleWidgets);
    setHasUnsavedChanges(true);
  };

  // Size presets based on widget size property (12-column grid, 40px rows)
  const getWidgetDimensions = (widgetId, breakpoint) => {
    const widget = WIDGET_REGISTRY[widgetId];
    if (!widget) return { w: 2, h: 3, minW: 2, minH: 3 };

    // Define dimensions based on widget size and category
    // Heights: h * 40px (3 = 120px for compact metric cards)
    // Width uses 12-column grid (2 = 1/6, 4 = 1/3, 6 = 1/2, etc.)
    const sizePresets = {
      small: { w: 2, h: 3, minW: 2, minH: 3 },      // Metric cards (120px height)
      medium: { w: 4, h: 7, minW: 3, minH: 5 },     // Charts, status panels
      large: { w: 4, h: 8, minW: 3, minH: 5 },      // Activity feeds, large charts
    };

    // Adjust width for smaller breakpoints (same proportions)
    const breakpointMultipliers = {
      lg: 1,      // 12 cols
      md: 1,      // 8 cols - keep same sizes
      sm: 1,      // 4 cols
      xs: 1,      // 4 cols
      xxs: 1,     // 2 cols
    };

    const preset = sizePresets[widget.size] || sizePresets.small;
    return {
      ...preset,
      w: Math.max(preset.w * breakpointMultipliers[breakpoint], preset.minW),
    };
  };

  // Add widget
  const addWidget = (widgetId) => {
    const currentWidgets = pendingVisibleWidgets || visibleWidgets;
    if (!currentWidgets.includes(widgetId)) {
      const newVisibleWidgets = [...currentWidgets, widgetId];
      setPendingVisibleWidgets(newVisibleWidgets);

      // Add default layout for new widget
      const newLayouts = { ...(pendingLayouts || layouts) };
      Object.keys(newLayouts).forEach(breakpoint => {
        if (!newLayouts[breakpoint].find(item => item.i === widgetId)) {
          // Try to find in DEFAULT_LAYOUTS first, otherwise use size presets
          const defaultItem = DEFAULT_LAYOUTS[breakpoint]?.find(item => item.i === widgetId);
          const dimensions = defaultItem || { i: widgetId, x: 0, ...getWidgetDimensions(widgetId, breakpoint) };

          // Place at the bottom
          const maxY = Math.max(...newLayouts[breakpoint].map(item => item.y + item.h), 0);
          newLayouts[breakpoint] = [
            ...newLayouts[breakpoint],
            { ...dimensions, i: widgetId, y: maxY },
          ];
        }
      });
      setPendingLayouts(newLayouts);
      setHasUnsavedChanges(true);
    }
    setShowWidgetPicker(false);
  };

  return (
    <div ref={containerRef} className="relative">
      {/* Edit Mode Banner */}
      {isEditMode && (
        <div className="sticky top-0 z-20 mb-4 bg-gradient-to-r from-olive-600 to-olive-500 dark:from-olive-700 dark:to-olive-600 text-white px-4 py-3 rounded-xl shadow-lg animate-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            {/* Left side - status info */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Cog6ToothIcon className="w-5 h-5 animate-spin-slow" />
                <span className="font-semibold">Customizing Dashboard</span>
              </div>
              <span className="text-olive-100 text-sm">
                {currentVisibleWidgets.length} widget{currentVisibleWidgets.length !== 1 ? 's' : ''} active
              </span>
              {hasUnsavedChanges && (
                <span className="flex items-center gap-1 text-sm bg-white/20 px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 bg-warning-300 rounded-full animate-pulse" />
                  Unsaved
                </span>
              )}
            </div>

            {/* Right side - action buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setShowWidgetPicker(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-medium transition-colors"
              >
                <PlusIcon className="w-4 h-4" />
                Add Widget
              </button>
              <button
                onClick={resetToDefault}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-medium transition-colors"
              >
                <ArrowPathIcon className="w-4 h-4" />
                Reset
              </button>
              <div className="hidden sm:block w-px h-6 bg-white/30 mx-1" />
              <button
                onClick={cancelChanges}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-medium transition-colors"
              >
                <XMarkIcon className="w-4 h-4" />
                Cancel
              </button>
              <button
                onClick={saveChanges}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-olive-700 hover:bg-olive-50 rounded-lg text-sm font-semibold transition-colors shadow-sm"
              >
                <CheckIcon className="w-4 h-4" />
                Save Layout
              </button>
            </div>
          </div>

          {/* Help text */}
          <p className="text-olive-100 text-xs mt-2 sm:hidden">
            Drag widgets to rearrange, resize from corners
          </p>
        </div>
      )}

      {/* Customize Button (when not in edit mode) */}
      {!isEditMode && (
        <div className="flex justify-end mb-4">
          <button
            onClick={enterEditMode}
            className="
              flex items-center gap-2 px-4 py-2.5 rounded-xl
              bg-white dark:bg-surface-700
              backdrop-blur-sm
              border border-surface-200/50 dark:border-surface-700/50
              shadow-sm hover:shadow-md
              text-surface-700 dark:text-surface-200 font-medium text-sm
              transition-all duration-200 ease-[var(--ease-tahoe)]
              hover:-translate-y-px
            "
          >
            <Cog6ToothIcon className="w-4 h-4" />
            Customize Dashboard
          </button>
        </div>
      )}

      {/* Grid Layout - 12 columns with 40px rows for finer resize increments */}
      {mounted && (
        <GridLayout
          className="layout"
          width={width}
          layout={layout}
          gridConfig={{
            cols,
            rowHeight: 40,
            margin: [16, 16],
            containerPadding: [0, 0],
          }}
          dragConfig={{
            enabled: isEditMode,
            handle: '.widget-drag-handle',
          }}
          resizeConfig={{
            enabled: isEditMode,
          }}
          compactor={verticalCompactor}
          onLayoutChange={(newLayout) => {
            if (isEditMode) {
              // Update the layout for the current breakpoint
              const newLayouts = { ...filteredLayouts, [breakpoint]: newLayout };
              setPendingLayouts(newLayouts);
              setHasUnsavedChanges(true);
            }
          }}
        >
          {currentVisibleWidgets.map((widgetId) => (
            <div key={widgetId} className="widget-container">
              <Widget
                id={widgetId}
                title={WIDGET_REGISTRY[widgetId]?.title || widgetId}
                isEditMode={isEditMode}
                onRemove={() => removeWidget(widgetId)}
              >
                {renderWidget ? renderWidget(widgetId) : null}
              </Widget>
            </div>
          ))}
        </GridLayout>
      )}

      {/* Widget Picker Modal */}
      {showWidgetPicker && (
        <WidgetPicker
          visibleWidgets={currentVisibleWidgets}
          onAdd={addWidget}
          onClose={() => setShowWidgetPicker(false)}
        />
      )}
    </div>
  );
}

// Widget wrapper component
function Widget({ id, title, isEditMode, onRemove, children }) {
  const widgetInfo = WIDGET_REGISTRY[id];
  const IconComponent = widgetInfo?.icon;

  // Color classes for widget icons in edit mode header
  const iconColorClasses = {
    aura: 'text-aura-500',
    olive: 'text-olive-500',
    critical: 'text-critical-500',
    warning: 'text-warning-500',
    surface: 'text-surface-500',
  };

  return (
    <div
      className={`
        h-full w-full rounded-xl overflow-hidden
        glass-card
        transition-all duration-200 ease-[var(--ease-tahoe)]
        ${isEditMode ? 'ring-2 ring-olive-500/50 ring-offset-2 dark:ring-offset-surface-900' : ''}
      `}
    >
      {/* Widget Header (only visible in edit mode) */}
      {isEditMode && (
        <div className="widget-drag-handle flex items-center justify-between px-3 py-2 bg-white dark:bg-surface-800 border-b border-surface-100/50 dark:border-surface-700/30 cursor-move select-none">
          <div className="flex items-center gap-2">
            {/* Drag handle dots */}
            <div className="flex flex-col gap-0.5 opacity-60">
              <div className="flex gap-0.5">
                <span className="w-1 h-1 rounded-full bg-surface-400" />
                <span className="w-1 h-1 rounded-full bg-surface-400" />
              </div>
              <div className="flex gap-0.5">
                <span className="w-1 h-1 rounded-full bg-surface-400" />
                <span className="w-1 h-1 rounded-full bg-surface-400" />
              </div>
            </div>
            {/* Widget icon */}
            {IconComponent && (
              <IconComponent className={`w-4 h-4 ${iconColorClasses[widgetInfo?.color] || 'text-surface-500'}`} />
            )}
            <span className="text-sm font-medium text-surface-700 dark:text-surface-300 truncate">
              {title}
            </span>
          </div>
          <button
            onMouseDown={(e) => {
              // Prevent drag from starting when clicking remove button
              e.stopPropagation();
            }}
            onClick={(e) => {
              e.stopPropagation();
              e.preventDefault();
              onRemove();
            }}
            className="p-1.5 hover:bg-critical-100 dark:hover:bg-critical-900/30 rounded-lg text-surface-400 hover:text-critical-600 dark:hover:text-critical-400 transition-colors"
            aria-label={`Remove ${title} widget`}
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Widget Content */}
      <div className={`h-full ${isEditMode ? 'pointer-events-none opacity-80' : ''}`}>
        {children}
      </div>
    </div>
  );
}

// Widget Picker Modal
function WidgetPicker({ visibleWidgets, onAdd, onClose }) {
  const availableWidgets = Object.values(WIDGET_REGISTRY).filter(
    widget => !visibleWidgets.includes(widget.id)
  );

  // Handle escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const categories = {
    metrics: 'Metric Cards',
    charts: 'Charts',
    feed: 'Activity Feeds',
    status: 'Status Panels',
    actions: 'Quick Actions',
    security: 'Security',
    compliance: 'Compliance',
    cost: 'Cost & Infrastructure',
  };

  const categoryOrder = ['metrics', 'charts', 'status', 'security', 'compliance', 'cost', 'feed', 'actions'];

  const groupedWidgets = availableWidgets.reduce((acc, widget) => {
    const category = widget.category || 'other';
    if (!acc[category]) acc[category] = [];
    acc[category].push(widget);
    return acc;
  }, {});

  // Color classes for widget icons
  const colorClasses = {
    aura: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400 group-hover:bg-aura-200 dark:group-hover:bg-aura-900/50',
    olive: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400 group-hover:bg-olive-200 dark:group-hover:bg-olive-900/50',
    critical: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400 group-hover:bg-critical-200 dark:group-hover:bg-critical-900/50',
    warning: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400 group-hover:bg-warning-200 dark:group-hover:bg-warning-900/50',
    surface: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400 group-hover:bg-surface-200 dark:group-hover:bg-surface-600',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 glass-backdrop"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="
        relative w-full max-w-2xl max-h-[85vh] overflow-hidden
        bg-white/95 dark:bg-surface-800/95
        backdrop-blur-xl backdrop-saturate-150
        rounded-2xl
        border border-white/50 dark:border-surface-700/50
        shadow-[var(--shadow-glass-hover)]
        animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]
      ">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30">
          <div>
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Add Widget
            </h2>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">
              Select a widget to add to your dashboard
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
            aria-label="Close modal"
          >
            <XMarkIcon className="w-5 h-5 text-surface-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(85vh-100px)]">
          {availableWidgets.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-olive-100 dark:bg-olive-900/30 flex items-center justify-center">
                <CheckIcon className="w-8 h-8 text-olive-600 dark:text-olive-400" />
              </div>
              <p className="text-surface-900 dark:text-surface-100 font-medium">All widgets active</p>
              <p className="text-surface-500 text-sm mt-1">Every available widget is already on your dashboard.</p>
            </div>
          ) : (
            <div className="space-y-8">
              {categoryOrder.map((category) => {
                const widgets = groupedWidgets[category];
                if (!widgets || widgets.length === 0) return null;

                return (
                  <div key={category}>
                    <h3 className="text-xs font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-3">
                      {categories[category] || category}
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {widgets.map((widget) => {
                        const IconComponent = widget.icon || PlusIcon;
                        return (
                          <button
                            key={widget.id}
                            onClick={() => onAdd(widget.id)}
                            className="
                              flex items-start gap-4 p-4 rounded-xl text-left group
                              bg-white dark:bg-surface-800
                              border border-surface-200/50 dark:border-surface-700/50
                              hover:bg-surface-50 dark:hover:bg-surface-700
                              hover:border-olive-400/50 dark:hover:border-olive-600/50
                              hover:shadow-md hover:-translate-y-px
                              transition-all duration-200 ease-[var(--ease-tahoe)]
                            "
                          >
                            <div className={`w-11 h-11 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${colorClasses[widget.color] || colorClasses.surface}`}>
                              <IconComponent className="w-5 h-5" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-surface-900 dark:text-surface-100 text-sm">
                                {widget.title}
                              </p>
                              <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5 line-clamp-2">
                                {widget.description}
                              </p>
                              <span className="inline-block mt-2 text-xs font-medium text-olive-600 dark:text-olive-400 bg-olive-50 dark:bg-olive-900/30 px-2 py-0.5 rounded-full capitalize">
                                {widget.size}
                              </span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
