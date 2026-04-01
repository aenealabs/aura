/**
 * Trust Center Page
 *
 * Main dashboard for AI Trust Center visibility into Constitutional AI,
 * autonomy configuration, safety metrics, and audit decisions.
 *
 * 5 Tabs:
 * - Overview: System status, compliance score, key metrics
 * - Principles: Constitutional AI principles browser
 * - Autonomy: Current autonomy level and HITL configuration
 * - Metrics: Safety metrics with time series charts
 * - Audit: Decision audit timeline
 */

import { useState, useCallback, memo, useRef, useEffect } from 'react';
import {
  ShieldCheckIcon,
  ScaleIcon,
  ChartBarIcon,
  ClipboardDocumentListIcon,
  CpuChipIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  TableCellsIcon,
  DocumentCheckIcon,
  CodeBracketIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';
import { useTrustCenter } from '../../hooks/useTrustCenter';
import { MetricPeriods } from '../../services/trustCenterApi';
import { exportTrustCenterReport, ExportFormats } from '../../services/trustCenterExport';
import { useToast } from '../ui/Toast';

// Tab components
import OverviewTab from './OverviewTab';
import PrinciplesTab from './PrinciplesTab';
import AutonomyTab from './AutonomyTab';
import MetricsTab from './MetricsTab';
import AuditTab from './AuditTab';

// Tab definitions
const TABS = [
  { id: 'overview', label: 'Overview', icon: ShieldCheckIcon },
  { id: 'principles', label: 'Principles', icon: ScaleIcon },
  { id: 'autonomy', label: 'Autonomy', icon: CpuChipIcon },
  { id: 'metrics', label: 'Metrics', icon: ChartBarIcon },
  { id: 'audit', label: 'Audit', icon: ClipboardDocumentListIcon },
];

// Period options
const PERIOD_OPTIONS = [
  { value: MetricPeriods.DAY, label: '24h' },
  { value: MetricPeriods.WEEK, label: '7d' },
  { value: MetricPeriods.MONTH, label: '30d' },
];

/**
 * Tab Button Component
 */
const TabButton = memo(function TabButton({ tab, isActive, onClick }) {
  const Icon = tab.icon;

  return (
    <button
      onClick={() => onClick(tab.id)}
      className={`
        flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium
        transition-all duration-200 ease-[var(--ease-tahoe)]
        ${isActive
          ? 'bg-white dark:bg-surface-700 text-aura-600 dark:text-aura-400 shadow-sm'
          : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-white/50 dark:hover:bg-surface-700/50'
        }
      `}
      aria-selected={isActive}
      role="tab"
    >
      <Icon className="w-4 h-4" />
      {tab.label}
    </button>
  );
});

/**
 * Status Badge Component
 */
const StatusBadge = memo(function StatusBadge({ status }) {
  const statusStyles = {
    healthy: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    warning: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    unknown: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
  };

  const statusLabels = {
    healthy: 'All Systems Operational',
    warning: 'Minor Issues Detected',
    critical: 'Critical Issues',
    unknown: 'Status Unknown',
  };

  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusStyles[status] || statusStyles.unknown}`}>
      <span className={`w-2 h-2 rounded-full mr-2 ${status === 'healthy' ? 'bg-olive-500' : status === 'warning' ? 'bg-warning-500' : status === 'critical' ? 'bg-critical-500' : 'bg-surface-400'}`} />
      {statusLabels[status] || statusLabels.unknown}
    </span>
  );
});

/**
 * Export Dropdown Component
 */
const ExportDropdown = memo(function ExportDropdown({ onExport, loading, data, period }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const exportOptions = [
    {
      id: ExportFormats.PDF,
      label: 'PDF Report',
      description: 'Executive summary for audits & board meetings',
      icon: DocumentTextIcon,
    },
    {
      id: ExportFormats.CSV,
      label: 'CSV Data',
      description: 'Tabular data for spreadsheets & analysis',
      icon: TableCellsIcon,
    },
    {
      id: ExportFormats.COMPLIANCE,
      label: 'Compliance Package',
      description: 'SOC2/CMMC audit evidence with attestations',
      icon: DocumentCheckIcon,
    },
    {
      id: ExportFormats.JSON,
      label: 'JSON Export',
      description: 'Raw data for API integrations',
      icon: CodeBracketIcon,
    },
  ];

  const handleExportClick = async (format) => {
    setIsOpen(false);
    await onExport(format, data, period);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading}
        className="
          flex items-center gap-2 px-4 py-2 rounded-lg
          bg-aura-500 hover:bg-aura-600 text-white
          font-medium text-sm
          transition-all duration-200
          disabled:opacity-50 disabled:cursor-not-allowed
        "
      >
        <ArrowDownTrayIcon className="w-4 h-4" />
        Export
        <ChevronDownIcon className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="
          absolute right-0 mt-2 w-72 z-50
          bg-white dark:bg-surface-800
          border border-surface-200 dark:border-surface-700
          rounded-xl shadow-lg
          overflow-hidden
        ">
          <div className="p-2">
            {exportOptions.map((option) => {
              const Icon = option.icon;
              return (
                <button
                  key={option.id}
                  onClick={() => handleExportClick(option.id)}
                  className="
                    w-full flex items-start gap-3 p-3 rounded-lg
                    text-left
                    hover:bg-surface-50 dark:hover:bg-surface-700
                    transition-colors duration-150
                  "
                >
                  <div className="p-2 rounded-lg bg-aura-50 dark:bg-aura-900/20">
                    <Icon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
                  </div>
                  <div>
                    <div className="font-medium text-surface-900 dark:text-surface-100">
                      {option.label}
                    </div>
                    <div className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                      {option.description}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
});

/**
 * Main Trust Center Page Component
 */
export default function TrustCenterPage() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { toast } = useToast();

  const {
    // Data
    status,
    principles,
    autonomy,
    metrics,
    decisions,

    // Computed values
    overallStatus,
    complianceScore,
    criticalPrinciples,
    principlesByCategory,
    metricsSummary,
    chartData,

    // Loading states
    isLoading,
    loadingStatus,
    loadingPrinciples,
    loadingAutonomy,
    loadingMetrics,
    loadingDecisions,
    loadingExport,

    // Error
    error,

    // Filters
    metricsPeriod,
    principlesFilter,
    decisionsPage,
    decisionsFilter,

    // Actions
    setPeriod,
    setPrinciplesFilter,
    setDecisionsFilter,
    refreshData,
    loadMoreDecisions,
    loadPreviousDecisions,
  } = useTrustCenter();

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await refreshData();
      toast.success('Trust Center refreshed');
    } catch (err) {
      toast.error('Failed to refresh data');
    } finally {
      setIsRefreshing(false);
    }
  }, [refreshData, toast]);

  const handleExport = async (format, _data, period) => {
    try {
      const exportData = {
        status,
        principles,
        autonomy,
        metrics,
        decisions,
        period,
      };
      const result = await exportTrustCenterReport(format, exportData);
      if (!result.success) {
        console.error('Export failed:', result.error);
      }
    } catch (err) {
      console.error('Export error:', err);
    }
  };

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              AI Trust Center
            </h1>
            <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
              Constitutional AI safety, autonomy configuration, and compliance monitoring
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Status Badge */}
            <StatusBadge status={overallStatus} />

            {/* Refresh Button */}
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="
                p-2 rounded-lg glass-card-subtle
                text-surface-600 dark:text-surface-400
                hover:text-surface-900 dark:hover:text-surface-100
                transition-all duration-200
                disabled:opacity-50
              "
              aria-label="Refresh data"
            >
              <ArrowPathIcon className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>

            {/* Export Dropdown */}
            <ExportDropdown
              onExport={handleExport}
              loading={loadingExport}
              data={{ status, principles, autonomy, metrics, decisions }}
              period={metricsPeriod}
            />
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="p-4 rounded-xl bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800">
            <p className="text-critical-700 dark:text-critical-400">{error}</p>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="glass-card-subtle p-1.5 rounded-2xl inline-flex gap-1" role="tablist">
          {TABS.map((tab) => (
            <TabButton
              key={tab.id}
              tab={tab}
              isActive={activeTab === tab.id}
              onClick={setActiveTab}
            />
          ))}
        </div>

        {/* Legend and Period Selector (for Metrics tab) */}
        {activeTab === 'metrics' && (
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            {/* Status Legend */}
            <div className="inline-flex items-center gap-6 glass-card-subtle rounded-xl px-4 py-3">
              <span className="text-sm font-medium text-surface-600 dark:text-surface-300">Status Legend:</span>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-olive-500" />
                  <span className="text-xs text-surface-600 dark:text-surface-400">Healthy (≥90% of target)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-warning-500" />
                  <span className="text-xs text-surface-600 dark:text-surface-400">Warning (60-89% of target)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-critical-500" />
                  <span className="text-xs text-surface-600 dark:text-surface-400">Critical (&lt;60% of target)</span>
                </div>
              </div>
            </div>

            {/* Period Selector */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-surface-500 dark:text-surface-400">Period:</span>
              <div className="inline-flex gap-1 p-1 rounded-lg glass-card-subtle">
                {PERIOD_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setPeriod(option.value)}
                    className={`
                      px-3 py-1.5 rounded-md text-sm font-medium
                      transition-all duration-200
                      ${metricsPeriod === option.value
                        ? 'bg-aura-500 text-white'
                        : 'text-surface-600 dark:text-surface-400 hover:bg-white/50 dark:hover:bg-surface-700/50'
                      }
                    `}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab Content */}
        <div className="mt-6 pb-20" role="tabpanel">
          {activeTab === 'overview' && (
            <OverviewTab
              status={status}
              complianceScore={complianceScore}
              metrics={metricsSummary}
              principles={principles}
              autonomy={autonomy}
              loading={loadingStatus || loadingMetrics}
            />
          )}

          {activeTab === 'principles' && (
            <PrinciplesTab
              principles={principles}
              principlesByCategory={principlesByCategory}
              criticalPrinciples={criticalPrinciples}
              filter={principlesFilter}
              setFilter={setPrinciplesFilter}
              loading={loadingPrinciples}
            />
          )}

          {activeTab === 'autonomy' && (
            <AutonomyTab
              autonomy={autonomy}
              loading={loadingAutonomy}
            />
          )}

          {activeTab === 'metrics' && (
            <MetricsTab
              metrics={metrics}
              metricsSummary={metricsSummary}
              chartData={chartData}
              period={metricsPeriod}
              loading={loadingMetrics}
            />
          )}

          {activeTab === 'audit' && (
            <AuditTab
              decisions={decisions}
              filter={decisionsFilter}
              setFilter={setDecisionsFilter}
              page={decisionsPage}
              onNextPage={loadMoreDecisions}
              onPrevPage={loadPreviousDecisions}
              loading={loadingDecisions}
            />
          )}
        </div>
      </div>
    </div>
  );
}
