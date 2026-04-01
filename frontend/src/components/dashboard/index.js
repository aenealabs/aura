/**
 * Project Aura - Dashboard Components
 *
 * Exports all dashboard-related components for easy importing.
 *
 * @module components/dashboard
 */

// MetricCard components
export {
  default as DashboardMetricCard,
  MetricCardGrid,
  MetricCardSkeleton,
  MetricCardError,
  TrendIndicator,
  Sparkline,
  StatusBadge,
} from './MetricCard';

// Dashboard Editor components (ADR-064)
export { default as DashboardEditor } from './DashboardEditor';
export { default as WidgetLibrary } from './WidgetLibrary';
export { default as ShareDashboardModal } from './ShareDashboardModal';
export { default as CustomWidgetBuilder } from './CustomWidgetBuilder';
export { default as ScheduleReportModal } from './ScheduleReportModal';

// Embeddable Dashboard (ADR-064 Phase 3)
export {
  default as EmbeddableDashboard,
  EmbedMode,
  EmbedTheme,
  useEmbeddedDashboard,
} from './EmbeddableDashboard';

// Widget Registry exports
export {
  WidgetType,
  WidgetCategory,
  UserRole,
  WIDGET_CATALOG,
  CATEGORY_LABELS,
  ROLE_DEFAULT_CONFIGS,
  getWidgetsByCategory,
  getWidgetById,
  getCategorizedWidgets,
} from './widgetRegistry';

// Scanner Widgets (ADR-084)
export {
  // P0 Widgets
  FindingsBySeverityWidget,
  ActiveScansWidget,
  ScanPipelineProgressWidget,
  TruePositiveRateWidget,
  LLMTokenSpendWidget,
  ScannerAlarmStatusWidget,
  RecentScanActivityWidget,
  FindingsRequiringApprovalWidget,
  // P1 Widgets
  ScanDurationTrendWidget,
  StageDurationWaterfallWidget,
  FindingsByCWEWidget,
  LLMLatencyWidget,
  ConcurrentUtilizationWidget,
  CriticalFindingsTrendWidget,
  ScanQueueDepthWidget,
  // P2 Widgets
  CandidateFunnelWidget,
  FindingsByLanguageWidget,
  VerificationStatusWidget,
  ScanDepthDistributionWidget,
  CleanupActivityWidget,
  // Shared
  SEVERITY_COLORS,
  SeverityBadge,
  WidgetSkeleton,
  WidgetError,
  WidgetCard,
} from './widgets/scanner';
