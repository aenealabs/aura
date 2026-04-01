/**
 * CapabilityGraphPage Component (ADR-071)
 *
 * Full-page view for the Cross-Agent Capability Graph.
 * Combines CapabilityGraph, CapabilityGraphFilters, and CapabilityDetailDrawer.
 *
 * @module components/capability/CapabilityGraphPage
 */

import React, { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  DocumentArrowDownIcon,
  Cog6ToothIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';

import { CapabilityGraph } from './CapabilityGraph';
import CapabilityGraphFilters from './CapabilityGraphFilters';
import CapabilityDetailDrawer from './CapabilityDetailDrawer';
import { useCapabilityGraph } from './useCapabilityGraph';

/**
 * AnalysisSummaryCard - Quick stat display
 */
function AnalysisSummaryCard({ label, value, icon: Icon, variant = 'default' }) {
  const variants = {
    default: 'bg-white dark:bg-surface-800',
    warning: 'bg-white dark:bg-surface-800',
    critical: 'bg-white dark:bg-surface-800',
    success: 'bg-white dark:bg-surface-800',
  };

  const iconColors = {
    default: 'text-aura-600 dark:text-aura-400',
    warning: 'text-warning-600 dark:text-warning-400',
    critical: 'text-critical-600 dark:text-critical-400',
    success: 'text-olive-600 dark:text-olive-400',
  };

  return (
    <div
      className={`
        ${variants[variant]}
        rounded-xl border border-surface-200 dark:border-surface-700 p-4
      `}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-surface-600 dark:text-surface-400">{label}</p>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100 mt-1">
            {value}
          </p>
        </div>
        {Icon && (
          <div className={`p-2 rounded-lg bg-surface-100 dark:bg-surface-700`}>
            <Icon className={`w-5 h-5 ${iconColors[variant]}`} />
          </div>
        )}
      </div>
    </div>
  );
}

AnalysisSummaryCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  icon: PropTypes.elementType,
  variant: PropTypes.oneOf(['default', 'warning', 'critical', 'success']),
};

/**
 * CapabilityGraphPage - Main component
 *
 * @param {Object} props
 * @param {Function} [props.onBack] - Callback for back navigation
 * @param {Function} [props.fetchNodeDetails] - Function to fetch node details
 * @param {string} [props.className] - Additional CSS classes
 */
function CapabilityGraphPage({
  onBack,
  fetchNodeDetails,
  className = '',
}) {
  // Graph hook
  const {
    data,
    loading,
    error,
    refresh,
    fetchEscalationPaths,
    fetchCoverageGaps,
    fetchToxicCombinations,
    runFullAnalysis,
    triggerSync,
    updateAgentCapabilities,
    fetchAgentDetails,
  } = useCapabilityGraph();

  // State
  const [selectedNode, setSelectedNode] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [filters, setFilters] = useState({
    agentTypes: [],
    classifications: ['safe', 'monitoring', 'dangerous', 'critical'],
    showEscalationPaths: true,
    showCoverageGaps: false,
    showToxicCombinations: false,
    riskThreshold: 0.5,
  });
  const [analysisResults, setAnalysisResults] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Handle node click
  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
    setIsDrawerOpen(true);
  }, []);

  // Handle filter change
  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
  }, []);

  // Clear all filters
  const handleClearFilters = useCallback(() => {
    setFilters({
      agentTypes: [],
      classifications: ['safe', 'monitoring', 'dangerous', 'critical'],
      showEscalationPaths: true,
      showCoverageGaps: false,
      showToxicCombinations: false,
      riskThreshold: 0.5,
    });
  }, []);

  // Run full analysis
  const handleRunAnalysis = useCallback(async () => {
    setIsAnalyzing(true);
    try {
      const results = await runFullAnalysis();
      setAnalysisResults(results);
    } catch (err) {
      console.error('Analysis failed:', err);
    } finally {
      setIsAnalyzing(false);
    }
  }, [runFullAnalysis]);

  // Sync policies
  const handleSync = useCallback(async () => {
    try {
      await triggerSync();
      await refresh();
    } catch (err) {
      console.error('Sync failed:', err);
    }
  }, [triggerSync, refresh]);

  // Handle permissions update
  const handlePermissionsUpdate = useCallback(async (data) => {
    try {
      await updateAgentCapabilities(data.agent_id, data.granted_tools);
      await refresh(); // Refresh graph after update
    } catch (err) {
      console.error('Failed to update permissions:', err);
      throw err;
    }
  }, [updateAgentCapabilities, refresh]);

  // Calculate summary stats
  const summaryStats = {
    totalAgents: data?.nodes?.filter((n) => n.type === 'agent').length || 0,
    totalTools: data?.nodes?.filter((n) => n.type !== 'agent').length || 0,
    escalationRisks: data?.nodes?.filter((n) => n.has_escalation_risk).length || 0,
    criticalTools: data?.nodes?.filter((n) => n.classification === 'critical').length || 0,
  };

  return (
    <div className={`h-screen overflow-y-auto bg-surface-50 dark:bg-surface-900 bg-grid-dot ${className}`}>
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {onBack && (
                <button
                  onClick={onBack}
                  className="p-2 rounded-lg text-surface-500 hover:text-surface-700
                             dark:hover:text-surface-300 hover:bg-surface-100
                             dark:hover:bg-surface-800 transition-colors"
                  aria-label="Go back"
                >
                  <ArrowLeftIcon className="w-5 h-5" />
                </button>
              )}
              <div>
                <h1 className="text-2xl lg:text-3xl font-bold text-surface-900 dark:text-surface-50">
                  Capability Graph
                </h1>
                <p className="text-sm text-surface-500 dark:text-surface-400">
                  Cross-agent capability analysis and visualization
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleRunAnalysis}
                disabled={isAnalyzing}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                           text-surface-700 dark:text-surface-300
                           bg-white dark:bg-surface-800 rounded-lg border
                           border-surface-200 dark:border-surface-700
                           hover:bg-surface-50 dark:hover:bg-surface-700
                           disabled:opacity-50 transition-colors"
              >
                <ChartBarIcon className={`w-4 h-4 ${isAnalyzing ? 'animate-pulse' : ''}`} />
                Run Analysis
              </button>
              <button
                onClick={handleSync}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                           text-surface-700 dark:text-surface-300
                           bg-white dark:bg-surface-800 rounded-lg border
                           border-surface-200 dark:border-surface-700
                           hover:bg-surface-50 dark:hover:bg-surface-700
                           disabled:opacity-50 transition-colors"
              >
                <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Sync Policies
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content with bottom padding for chat assistant */}
      <div className="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-32 overflow-x-visible">
        {/* Summary stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <AnalysisSummaryCard
            label="Total Agents"
            value={summaryStats.totalAgents}
            icon={ShieldCheckIcon}
            variant="default"
          />
          <AnalysisSummaryCard
            label="Total Tools"
            value={summaryStats.totalTools}
            icon={Cog6ToothIcon}
            variant="default"
          />
          <AnalysisSummaryCard
            label="Escalation Risks"
            value={summaryStats.escalationRisks}
            icon={ExclamationTriangleIcon}
            variant={summaryStats.escalationRisks > 0 ? 'critical' : 'success'}
          />
          <AnalysisSummaryCard
            label="Critical Tools"
            value={summaryStats.criticalTools}
            icon={ExclamationTriangleIcon}
            variant={summaryStats.criticalTools > 5 ? 'warning' : 'default'}
          />
        </div>

        {/* Main layout */}
        <div className="flex gap-6">
          {/* Filters sidebar */}
          <div className="w-80 flex-shrink-0">
            <CapabilityGraphFilters
              filters={filters}
              onFilterChange={handleFilterChange}
              onClearAll={handleClearFilters}
            />
          </div>

          {/* Graph area */}
          <div className="flex-1 min-w-0 overflow-visible">
            <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-visible">
              <CapabilityGraph
                width={1100}
                height={1200}
                onNodeClick={handleNodeClick}
                showControls={true}
                showLegend={true}
                filters={filters}
              />
            </div>
          </div>
        </div>

        {/* Analysis results panel (if analysis was run) */}
        {analysisResults && (
          <div className="mt-6 bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-6">
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
              Analysis Results
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Escalation paths */}
              <div>
                <h3 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  Escalation Paths ({analysisResults.escalation_paths?.length || 0})
                </h3>
                {analysisResults.escalation_paths?.length > 0 ? (
                  <ul className="space-y-2">
                    {analysisResults.escalation_paths.slice(0, 5).map((path, i) => (
                      <li
                        key={i}
                        className="text-sm p-2 rounded bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300"
                      >
                        Risk: {Math.round(path.risk_score * 100)}% - {path.steps?.join(' → ')}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-olive-600 dark:text-olive-400">
                    No escalation paths detected
                  </p>
                )}
              </div>

              {/* Coverage gaps */}
              <div>
                <h3 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  Coverage Gaps ({analysisResults.coverage_gaps?.length || 0})
                </h3>
                {analysisResults.coverage_gaps?.length > 0 ? (
                  <ul className="space-y-2">
                    {analysisResults.coverage_gaps.slice(0, 5).map((gap, i) => (
                      <li
                        key={i}
                        className="text-sm p-2 rounded bg-warning-50 dark:bg-warning-900/20 text-warning-700 dark:text-warning-300"
                      >
                        {gap.agent} - {gap.missing_capability}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-olive-600 dark:text-olive-400">
                    No coverage gaps detected
                  </p>
                )}
              </div>

              {/* Toxic combinations */}
              <div>
                <h3 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  Toxic Combinations ({analysisResults.toxic_combinations?.length || 0})
                </h3>
                {analysisResults.toxic_combinations?.length > 0 ? (
                  <ul className="space-y-2">
                    {analysisResults.toxic_combinations.slice(0, 5).map((combo, i) => (
                      <li
                        key={i}
                        className="text-sm p-2 rounded bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300"
                      >
                        {combo.tools?.join(' + ')} - {combo.reason}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-olive-600 dark:text-olive-400">
                    No toxic combinations detected
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      <CapabilityDetailDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        selectedNode={selectedNode}
        fetchDetails={fetchNodeDetails}
      />
    </div>
  );
}

CapabilityGraphPage.propTypes = {
  onBack: PropTypes.func,
  fetchNodeDetails: PropTypes.func,
  className: PropTypes.string,
};

export default CapabilityGraphPage;
