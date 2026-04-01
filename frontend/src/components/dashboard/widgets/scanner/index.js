/**
 * Scanner Widget Exports (ADR-084)
 *
 * All vulnerability scanner dashboard widgets.
 *
 * @module components/dashboard/widgets/scanner
 */

// P0 Widgets
export { FindingsBySeverityWidget } from './FindingsBySeverityWidget';
export { ActiveScansWidget } from './ActiveScansWidget';
export { ScanPipelineProgressWidget } from './ScanPipelineProgressWidget';
export { TruePositiveRateWidget } from './TruePositiveRateWidget';
export { LLMTokenSpendWidget } from './LLMTokenSpendWidget';
export { ScannerAlarmStatusWidget } from './ScannerAlarmStatusWidget';
export { RecentScanActivityWidget } from './RecentScanActivityWidget';
export { FindingsRequiringApprovalWidget } from './FindingsRequiringApprovalWidget';

// P1 Widgets
export { ScanDurationTrendWidget } from './ScanDurationTrendWidget';
export { StageDurationWaterfallWidget } from './StageDurationWaterfallWidget';
export { FindingsByCWEWidget } from './FindingsByCWEWidget';
export { LLMLatencyWidget } from './LLMLatencyWidget';
export { ConcurrentUtilizationWidget } from './ConcurrentUtilizationWidget';
export { CriticalFindingsTrendWidget } from './CriticalFindingsTrendWidget';
export { ScanQueueDepthWidget } from './ScanQueueDepthWidget';

// P2 Widgets
export { CandidateFunnelWidget } from './CandidateFunnelWidget';
export { FindingsByLanguageWidget, VerificationStatusWidget, ScanDepthDistributionWidget } from './DonutWidgets';
export { CleanupActivityWidget } from './CleanupActivityWidget';

// Shared components
export {
  SEVERITY_COLORS,
  ALARM_COLORS,
  STAGE_LABELS,
  STAGE_STATUS_COLORS,
  SeverityBadge,
  ConfidenceBadge,
  VerificationBadge,
  WidgetSkeleton,
  WidgetError,
  WidgetCard,
  formatDuration,
  formatRelativeTime,
  formatNumber,
} from './ScannerWidgetShared';
