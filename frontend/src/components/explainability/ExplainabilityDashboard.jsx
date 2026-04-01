/**
 * ExplainabilityDashboard Component (ADR-068)
 *
 * Main dashboard for the Universal Explainability Framework.
 * Combines DecisionExplorer, ReasoningViewer, ConfidenceVisualization,
 * AlternativesComparison, and ContradictionAlerts.
 *
 * @module components/explainability/ExplainabilityDashboard
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  ArrowLeftIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ArrowPathIcon,
  ChartBarIcon,
  LightBulbIcon,
  ExclamationTriangleIcon,
  DocumentMagnifyingGlassIcon,
} from '@heroicons/react/24/outline';

import DecisionExplorer from './DecisionExplorer';
import ReasoningViewer from './ReasoningViewer';
import ConfidenceVisualization from './ConfidenceVisualization';
import AlternativesComparison from './AlternativesComparison';
import ContradictionAlerts from './ContradictionAlerts';

/**
 * Tab configuration for the dashboard
 */
const TABS = [
  {
    id: 'decisions',
    label: 'Decision Explorer',
    icon: DocumentMagnifyingGlassIcon,
    description: 'Browse and search AI decisions',
  },
  {
    id: 'contradictions',
    label: 'Contradictions',
    icon: ExclamationTriangleIcon,
    description: 'View reasoning-action mismatches',
  },
];

/**
 * StatCard - Summary statistic display
 */
function StatCard({ label, value, change, changeType, icon: Icon }) {
  const getChangeColor = () => {
    if (!changeType) return 'text-surface-500';
    if (changeType === 'positive') return 'text-olive-600 dark:text-olive-400';
    if (changeType === 'negative') return 'text-critical-600 dark:text-critical-400';
    return 'text-surface-500';
  };

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-surface-600 dark:text-surface-400">{label}</p>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100 mt-1">
            {value}
          </p>
          {change !== undefined && (
            <p className={`text-sm mt-1 ${getChangeColor()}`}>
              {change > 0 ? '+' : ''}{change}% from last period
            </p>
          )}
        </div>
        {Icon && (
          <div className="p-3 rounded-lg bg-aura-100 dark:bg-aura-900/30">
            <Icon className="w-6 h-6 text-aura-600 dark:text-aura-400" />
          </div>
        )}
      </div>
    </div>
  );
}

StatCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  change: PropTypes.number,
  changeType: PropTypes.oneOf(['positive', 'negative', 'neutral']),
  icon: PropTypes.elementType,
};

/**
 * ConfidenceStatCard - Stat card with confidence threshold legend
 * Shows red/yellow/green thresholds for confidence interpretation
 */
function ConfidenceStatCard({ label, value, change, changeType, icon: Icon }) {
  // Parse numeric value from percentage string
  const numericValue = typeof value === 'string'
    ? parseFloat(value.replace('%', ''))
    : value * 100;

  // Determine status color based on confidence thresholds
  // Red: ≤69%, Yellow: 70-84%, Green: ≥85%
  const getStatusColor = () => {
    if (numericValue >= 85) return 'text-olive-600 dark:text-olive-400';
    if (numericValue >= 70 && numericValue <= 84) return 'text-warning-600 dark:text-warning-400';
    return 'text-critical-600 dark:text-critical-400';
  };

  const getChangeColor = () => {
    if (!changeType) return 'text-surface-500';
    if (changeType === 'positive') return 'text-olive-600 dark:text-olive-400';
    if (changeType === 'negative') return 'text-critical-600 dark:text-critical-400';
    return 'text-surface-500';
  };

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm text-surface-600 dark:text-surface-400">{label}</p>
          <p className={`text-2xl font-bold mt-1 ${getStatusColor()}`}>
            {value}
          </p>
          {change !== undefined && (
            <p className={`text-sm mt-1 ${getChangeColor()}`}>
              {change > 0 ? '+' : ''}{change}% from last period
            </p>
          )}
        </div>
        {Icon && (
          <div className="p-3 rounded-lg bg-aura-100 dark:bg-aura-900/30">
            <Icon className="w-6 h-6 text-aura-600 dark:text-aura-400" />
          </div>
        )}
      </div>

      {/* Confidence threshold legend */}
      <div className="mt-3 pt-3 border-t border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-critical-500"></span>
            <span className="text-surface-500 dark:text-surface-400">≤69%</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-warning-500"></span>
            <span className="text-surface-500 dark:text-surface-400">70-84%</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-olive-500"></span>
            <span className="text-surface-500 dark:text-surface-400">≥85%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

ConfidenceStatCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  change: PropTypes.number,
  changeType: PropTypes.oneOf(['positive', 'negative', 'neutral']),
  icon: PropTypes.elementType,
};

/**
 * DecisionDetailPanel - Side panel for decision details
 */
function DecisionDetailPanel({ decision, onClose }) {
  if (!decision) return null;

  return (
    <div className="fixed top-0 bottom-24 right-0 w-[600px] bg-white dark:bg-surface-900 border-l border-surface-200 dark:border-surface-700 shadow-xl overflow-y-auto z-50 rounded-bl-xl">
      {/* Header */}
      <div className="sticky top-0 bg-white dark:bg-surface-900 border-b border-surface-200 dark:border-surface-700 p-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          Decision Details
        </h2>
        <button
          onClick={onClose}
          className="p-2 rounded-lg text-surface-500 hover:text-surface-700 dark:hover:text-surface-300
                     hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
          aria-label="Close panel"
        >
          <ArrowLeftIcon className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="p-4 space-y-6">
        {/* Decision summary */}
        <div>
          <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">
            Summary
          </h3>
          <p className="text-surface-900 dark:text-surface-100 font-medium">
            {decision.title || decision.output}
          </p>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
            {decision.description}
          </p>
        </div>

        {/* Reasoning chain */}
        {decision.reasoningChain && (
          <ReasoningViewer decision={decision} />
        )}

        {/* Confidence visualization */}
        {decision.confidenceData && (
          <ConfidenceVisualization
            confidenceData={decision.confidenceData}
            reasoningSteps={decision.reasoningChain}
          />
        )}

        {/* Alternatives comparison */}
        {decision.alternatives && decision.alternatives.length > 0 && (
          <AlternativesComparison
            alternatives={decision.alternatives}
            selectedIndex={decision.selectedAlternativeIndex || 0}
            criteria={decision.criteria}
            decisionRationale={decision.rationale}
          />
        )}
      </div>
    </div>
  );
}

DecisionDetailPanel.propTypes = {
  decision: PropTypes.object,
  onClose: PropTypes.func.isRequired,
};

/**
 * ExplainabilityDashboard - Main component
 *
 * @param {Object} props
 * @param {Function} [props.fetchDecisions] - Function to fetch decisions
 * @param {Function} [props.fetchContradictions] - Function to fetch contradictions
 * @param {Function} [props.fetchStats] - Function to fetch dashboard stats
 * @param {Function} [props.onRefresh] - Callback for refresh button (with toast notifications)
 * @param {Function} [props.onResolveContradiction] - Callback for resolving contradictions
 * @param {Function} [props.onDismissContradiction] - Callback for dismissing contradictions
 * @param {Function} [props.onBack] - Callback for back navigation
 * @param {string} [props.className] - Additional CSS classes
 */
function ExplainabilityDashboard({
  fetchDecisions,
  fetchContradictions,
  fetchStats,
  onRefresh,
  onResolveContradiction,
  onDismissContradiction,
  onBack,
  className = '',
}) {
  // State
  const [activeTab, setActiveTab] = useState('decisions');
  const [decisions, setDecisions] = useState([]);
  const [contradictions, setContradictions] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedDecision, setSelectedDecision] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [filters, setFilters] = useState({
    agents: [],
    severities: [],
    timeRange: '7d',
  });

  // Fetch data on mount (initial load without toast)
  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [decisionsData, contradictionsData, statsData] = await Promise.all([
        fetchDecisions ? fetchDecisions(filters) : Promise.resolve([]),
        fetchContradictions ? fetchContradictions() : Promise.resolve([]),
        fetchStats ? fetchStats() : Promise.resolve(null),
      ]);

      setDecisions(decisionsData);
      setContradictions(contradictionsData);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load explainability data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchDecisions, fetchContradictions, fetchStats, filters]);

  // Handle refresh button click (with toast notifications)
  const handleRefresh = useCallback(async () => {
    setIsLoading(true);
    try {
      if (onRefresh) {
        // Use the provided refresh handler (includes toast notifications)
        const result = await onRefresh();
        if (result) {
          setDecisions(result.decisions || []);
          setContradictions(result.contradictions || []);
          setStats(result.stats || null);
        }
      } else {
        // Fallback to internal loadData
        await loadData();
      }
    } catch (error) {
      console.error('Failed to refresh data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [onRefresh, loadData]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle decision selection
  const handleSelectDecision = (decision) => {
    setSelectedDecision(decision);
  };

  // Handle filter changes from DecisionExplorer
  const handleFilterChange = (newFilters) => {
    setFilters((prev) => ({ ...prev, ...newFilters }));
  };

  // Default stats if not provided
  const displayStats = stats || {
    totalDecisions: decisions.length,
    avgConfidence: 0.82,
    activeContradictions: contradictions.filter((c) => c.status === 'active').length,
    resolvedToday: 5,
  };

  return (
    <div className={`h-screen overflow-y-auto bg-surface-50 dark:bg-surface-900 bg-grid-dot ${className}`}>
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl lg:text-3xl font-bold text-surface-900 dark:text-surface-50">
                Explainability Dashboard
              </h1>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Understand how Aura makes decisions
              </p>
            </div>

            <button
              onClick={handleRefresh}
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                         text-surface-700 dark:text-surface-300
                         bg-white dark:bg-surface-800 rounded-lg border
                         border-surface-200 dark:border-surface-700
                         hover:bg-surface-50 dark:hover:bg-surface-700
                         disabled:opacity-50 transition-colors"
            >
              <ArrowPathIcon className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Main content with bottom padding for chat assistant */}
      <div className="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-32">
        {/* Stats row */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Total Decisions"
            value={displayStats.totalDecisions.toLocaleString()}
            icon={DocumentMagnifyingGlassIcon}
          />
          <ConfidenceStatCard
            label="Avg Confidence"
            value={`${Math.round(displayStats.avgConfidence * 100)}%`}
            change={2.3}
            changeType="positive"
            icon={ChartBarIcon}
          />
          <StatCard
            label="Active Contradictions"
            value={displayStats.activeContradictions}
            changeType={displayStats.activeContradictions > 0 ? 'negative' : 'positive'}
            icon={ExclamationTriangleIcon}
          />
          <StatCard
            label="Resolved Today"
            value={displayStats.resolvedToday}
            change={15}
            changeType="positive"
            icon={LightBulbIcon}
          />
        </div>

        {/* Tabs */}
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
          <div className="border-b border-surface-200 dark:border-surface-700">
            <nav className="flex -mb-px">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`
                      flex items-center gap-2 px-6 py-4 text-sm font-medium
                      border-b-2 transition-colors
                      ${isActive
                        ? 'border-aura-600 text-aura-600 dark:text-aura-400'
                        : 'border-transparent text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200 hover:border-surface-300'
                      }
                    `}
                  >
                    <Icon className="w-5 h-5" />
                    {tab.label}
                    {tab.id === 'contradictions' && displayStats.activeContradictions > 0 && (
                      <span className="ml-2 px-2 py-0.5 text-xs font-medium rounded-full bg-critical-100 dark:bg-critical-900 text-critical-700 dark:text-critical-300">
                        {displayStats.activeContradictions}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Tab content - scrollable with max height */}
          <div className="p-6 max-h-[1200px] overflow-y-auto">
            {activeTab === 'decisions' && (
              <DecisionExplorer
                decisions={decisions}
                onViewDecision={handleSelectDecision}
                onFilterChange={handleFilterChange}
                isLoading={isLoading}
              />
            )}

            {activeTab === 'contradictions' && (
              <ContradictionAlerts
                contradictions={contradictions}
                onResolve={onResolveContradiction}
                onDismiss={onDismissContradiction}
                showResolved={false}
              />
            )}
          </div>
        </div>
      </div>

      {/* Decision detail panel */}
      {selectedDecision && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/20 dark:bg-black/40 z-40"
            onClick={() => setSelectedDecision(null)}
          />
          <DecisionDetailPanel
            decision={selectedDecision}
            onClose={() => setSelectedDecision(null)}
          />
        </>
      )}
    </div>
  );
}

ExplainabilityDashboard.propTypes = {
  fetchDecisions: PropTypes.func,
  fetchContradictions: PropTypes.func,
  fetchStats: PropTypes.func,
  onRefresh: PropTypes.func,
  onResolveContradiction: PropTypes.func,
  onDismissContradiction: PropTypes.func,
  onBack: PropTypes.func,
  className: PropTypes.string,
};

export default ExplainabilityDashboard;
