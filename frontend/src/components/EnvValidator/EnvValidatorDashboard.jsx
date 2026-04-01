/**
 * EnvValidatorDashboard - Main dashboard for Environment Validator
 *
 * Comprehensive view of environment validation status, drift detection,
 * and agent activity. Combines all EnvValidator widgets into a single
 * dashboard layout with drag-and-drop card reordering.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  DocumentPlusIcon,
  Bars3Icon,
  ChevronUpIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';
import { useToast } from '../ui/Toast';
import ValidationTimeline from './ValidationTimeline';
import ViolationHeatmap from './ViolationHeatmap';
import DriftStatusPanel from './DriftStatusPanel';
import AgentActivityFeed from './AgentActivityFeed';
import {
  getHealth,
  Environments,
} from '../../services/envValidatorApi';

// Summary card component
function SummaryCard({ title, value, subtitle, icon: Icon, status, loading }) {
  const statusColors = {
    healthy: 'text-olive-600 dark:text-olive-400',
    warning: 'text-warning-600 dark:text-warning-400',
    critical: 'text-critical-600 dark:text-critical-400',
    neutral: 'text-surface-600 dark:text-surface-400',
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card p-4 animate-pulse">
        <div className="flex items-center justify-between mb-3">
          <div className="h-4 bg-surface-200 dark:bg-surface-700 rounded w-1/2" />
          <div className="w-8 h-8 bg-surface-200 dark:bg-surface-700 rounded-lg" />
        </div>
        <div className="h-8 bg-surface-200 dark:bg-surface-700 rounded w-1/3 mb-2" />
        <div className="h-3 bg-surface-200 dark:bg-surface-700 rounded w-2/3" />
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-surface-500 dark:text-surface-400">
          {title}
        </span>
        <div className={`p-2 rounded-lg bg-surface-100 dark:bg-surface-700 ${statusColors[status]}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className={`text-2xl font-semibold ${statusColors[status]}`}>
        {value}
      </div>
      {subtitle && (
        <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
          {subtitle}
        </p>
      )}
    </div>
  );
}

// Draggable and resizable card wrapper
function DraggableCard({ id, children, onMoveUp, onMoveDown, canMoveUp, canMoveDown, isEditMode, height, onResize, minHeight = 280, maxHeight = 600 }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [startY, setStartY] = useState(0);
  const [startHeight, setStartHeight] = useState(height);

  const handleDragStart = (e) => {
    if (!isEditMode || isResizing) return;
    setIsDragging(true);
    e.dataTransfer.setData('text/plain', id);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragEnd = () => {
    setIsDragging(false);
  };

  const handleDragOver = (e) => {
    if (!isEditMode) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e) => {
    if (!isEditMode) return;
    e.preventDefault();
    const draggedId = e.dataTransfer.getData('text/plain');
    if (draggedId !== id) {
      // Emit custom event for parent to handle
      const event = new CustomEvent('cardDrop', { detail: { from: draggedId, to: id } });
      document.dispatchEvent(event);
    }
  };

  // Resize handlers
  const handleResizeStart = (e) => {
    if (!isEditMode) return;
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
    setStartY(e.clientY);
    setStartHeight(height);
  };

  const handleResizeMove = useCallback((e) => {
    if (!isResizing) return;
    const deltaY = e.clientY - startY;
    const newHeight = Math.max(minHeight, Math.min(maxHeight, startHeight + deltaY));
    onResize?.(id, newHeight);
  }, [isResizing, startY, startHeight, minHeight, maxHeight, onResize, id]);

  const handleResizeEnd = useCallback(() => {
    setIsResizing(false);
  }, []);

  // Add/remove global mouse listeners for resizing
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleResizeMove);
      document.addEventListener('mouseup', handleResizeEnd);
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
    }
    return () => {
      document.removeEventListener('mousemove', handleResizeMove);
      document.removeEventListener('mouseup', handleResizeEnd);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, handleResizeMove, handleResizeEnd]);

  return (
    <div
      draggable={isEditMode && !isResizing}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className={`
        relative group
        ${isDragging ? 'opacity-50 scale-95' : ''}
        ${isEditMode ? 'ring-2 ring-dashed ring-surface-300 dark:ring-surface-600 rounded-xl' : ''}
        transition-all duration-200
      `}
      style={{ height: height ? `${height}px` : undefined }}
    >
      {/* Drag handle and reorder controls */}
      {isEditMode && (
        <div className="absolute -top-2 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1 bg-white dark:bg-surface-700 rounded-full shadow-md border border-surface-200 dark:border-surface-600 px-2 py-1">
          <button
            onClick={onMoveUp}
            disabled={!canMoveUp}
            className="p-0.5 hover:bg-surface-100 dark:hover:bg-surface-600 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Move up"
          >
            <ChevronUpIcon className="w-4 h-4 text-surface-600 dark:text-surface-300" />
          </button>
          <div className="cursor-grab active:cursor-grabbing px-1">
            <Bars3Icon className="w-4 h-4 text-surface-400" />
          </div>
          <button
            onClick={onMoveDown}
            disabled={!canMoveDown}
            className="p-0.5 hover:bg-surface-100 dark:hover:bg-surface-600 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Move down"
          >
            <ChevronDownIcon className="w-4 h-4 text-surface-600 dark:text-surface-300" />
          </button>
        </div>
      )}

      {/* Card content */}
      <div className="h-full">{children}</div>

      {/* Resize handle at bottom */}
      {isEditMode && (
        <div
          onMouseDown={handleResizeStart}
          className="absolute bottom-0 left-0 right-0 h-3 cursor-ns-resize group/resize flex items-center justify-center"
        >
          <div className="w-16 h-1.5 rounded-full bg-surface-300 dark:bg-surface-600 group-hover/resize:bg-aura-500 transition-colors" />
        </div>
      )}
    </div>
  );
}

// Storage keys for card order and sizes
const CARD_ORDER_KEY = 'aura_env_validator_card_order';
const CARD_SIZES_KEY = 'aura_env_validator_card_sizes';

// Default card order
const DEFAULT_CARD_ORDER = {
  left: ['heatmap', 'timeline'],
  right: ['drift', 'activity'],
};

// Default card sizes (in pixels)
const DEFAULT_CARD_SIZES = {
  heatmap: 380,
  timeline: 400,
  drift: 380,
  activity: 400,
};

export default function EnvValidatorDashboard() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedEnv, setSelectedEnv] = useState(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [showNewValidation, setShowNewValidation] = useState(false);

  // Card order state with localStorage persistence
  const [cardOrder, setCardOrder] = useState(() => {
    try {
      const saved = localStorage.getItem(CARD_ORDER_KEY);
      return saved ? JSON.parse(saved) : DEFAULT_CARD_ORDER;
    } catch {
      return DEFAULT_CARD_ORDER;
    }
  });

  // Card sizes state with localStorage persistence
  const [cardSizes, setCardSizes] = useState(() => {
    try {
      const saved = localStorage.getItem(CARD_SIZES_KEY);
      return saved ? { ...DEFAULT_CARD_SIZES, ...JSON.parse(saved) } : DEFAULT_CARD_SIZES;
    } catch {
      return DEFAULT_CARD_SIZES;
    }
  });

  // Dashboard state
  const [summaryData, setSummaryData] = useState({
    totalValidations: 0,
    passRate: 0,
    activeBaselines: 0,
    driftAlerts: 0,
  });
  const [health, setHealth] = useState(null);

  // Save card order to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(CARD_ORDER_KEY, JSON.stringify(cardOrder));
    } catch (e) {
      console.warn('Failed to save card order:', e);
    }
  }, [cardOrder]);

  // Save card sizes to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(CARD_SIZES_KEY, JSON.stringify(cardSizes));
    } catch (e) {
      console.warn('Failed to save card sizes:', e);
    }
  }, [cardSizes]);

  // Handle card reordering
  const moveCard = (column, index, direction) => {
    const newOrder = { ...cardOrder };
    const cards = [...newOrder[column]];
    const newIndex = index + direction;
    if (newIndex >= 0 && newIndex < cards.length) {
      [cards[index], cards[newIndex]] = [cards[newIndex], cards[index]];
      newOrder[column] = cards;
      setCardOrder(newOrder);
    }
  };

  // Handle card resizing
  const handleCardResize = useCallback((cardId, newHeight) => {
    setCardSizes(prev => ({
      ...prev,
      [cardId]: newHeight,
    }));
  }, []);

  // Toggle edit mode
  const handleToggleEditMode = () => {
    if (isEditMode) {
      toast.success('Layout saved');
    }
    setIsEditMode(!isEditMode);
  };

  // Reset card order and sizes
  const handleResetOrder = () => {
    setCardOrder(DEFAULT_CARD_ORDER);
    setCardSizes(DEFAULT_CARD_SIZES);
    toast.info('Layout reset to default');
  };

  // Load dashboard data
  const loadData = useCallback(async () => {
    try {
      // Load health status
      const healthData = await getHealth(selectedEnv || 'dev').catch(() => null);
      setHealth(healthData);

      // Calculate summary from mock data (in production, these would be API calls)
      setSummaryData({
        totalValidations: 127,
        passRate: 94.5,
        activeBaselines: 45,
        driftAlerts: 3,
      });

    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, [toast, selectedEnv]);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => loadData(), 60000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Event handlers
  const handleSelectRun = (run) => {
    toast.info(`Viewing validation run ${run.run_id}`);
  };

  const handleCellClick = (ruleId, env) => {
    toast.info(`Viewing ${ruleId} violations in ${env}`);
  };

  const handleViewDiff = (event) => {
    toast.info(`Viewing diff for ${event.resource_name}`);
  };

  const handleRescan = (env) => {
    toast.info(`Starting drift scan for ${env}...`);
  };

  // Refresh handler - matches RedTeam dashboard pattern
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadData();
    setIsRefreshing(false);
    toast.success('Dashboard refreshed');
  };

  // New validation handler
  const handleNewValidation = () => {
    setShowNewValidation(true);
    toast.info('Select an environment to validate');
  };

  return (
    <div className="min-h-screen bg-surface-50 dark:bg-surface-900 bg-grid-dot">
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ShieldCheckIcon className="w-8 h-8 text-aura-500" />
              <div>
                <h1 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
                  Environment Validator
                </h1>
                <p className="text-sm text-surface-500 dark:text-surface-400">
                  Cross-environment configuration validation
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Refresh button - leftmost */}
              <button
                type="button"
                onClick={handleRefresh}
                disabled={isRefreshing}
                className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
              >
                <ArrowPathIcon className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                Refresh
              </button>

              {/* Environment filter */}
              <select
                value={selectedEnv || ''}
                onChange={(e) => setSelectedEnv(e.target.value || null)}
                className="px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300 text-sm"
              >
                <option value="">All Environments</option>
                {Environments.map((env) => (
                  <option key={env} value={env}>{env.toUpperCase()}</option>
                ))}
              </select>

              {/* Edit layout button */}
              <button
                type="button"
                onClick={handleToggleEditMode}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors duration-200 ${
                  isEditMode
                    ? 'bg-olive-500 border-olive-500 text-white hover:bg-olive-600'
                    : 'border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-600'
                }`}
              >
                <Bars3Icon className="w-4 h-4" />
                <span className="text-sm">{isEditMode ? 'Save Layout' : 'Edit Layout'}</span>
              </button>

              {/* Reset button (only in edit mode) */}
              {isEditMode && (
                <button
                  type="button"
                  onClick={handleResetOrder}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-600 transition-colors"
                >
                  <ArrowPathIcon className="w-4 h-4" />
                  <span className="text-sm">Reset</span>
                </button>
              )}

              {/* New validation button */}
              <button
                type="button"
                onClick={handleNewValidation}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-aura-500 text-white hover:bg-aura-600 transition-colors font-medium"
              >
                <DocumentPlusIcon className="w-4 h-4" />
                New Validation
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Edit mode banner */}
      {isEditMode && (
        <div className="bg-olive-500 text-white px-4 py-2">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <Bars3Icon className="w-4 h-4" />
              <span>Drag cards to reorder, drag bottom edge to resize. Click &quot;Save Layout&quot; when done.</span>
            </div>
          </div>
        </div>
      )}

      {/* Dashboard content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Summary cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <SummaryCard
            title="Total Validations"
            value={summaryData.totalValidations}
            subtitle="Last 30 days"
            icon={ShieldCheckIcon}
            status="neutral"
            loading={loading}
          />
          <SummaryCard
            title="Pass Rate"
            value={`${summaryData.passRate}%`}
            subtitle="Last 30 days"
            icon={ShieldCheckIcon}
            status={summaryData.passRate >= 90 ? 'healthy' : summaryData.passRate >= 70 ? 'warning' : 'critical'}
            loading={loading}
          />
          <SummaryCard
            title="Active Baselines"
            value={summaryData.activeBaselines}
            subtitle="Across all environments"
            icon={ShieldCheckIcon}
            status="neutral"
            loading={loading}
          />
          <SummaryCard
            title="Drift Alerts"
            value={summaryData.driftAlerts}
            subtitle="Unresolved"
            icon={ExclamationTriangleIcon}
            status={summaryData.driftAlerts === 0 ? 'healthy' : summaryData.driftAlerts <= 3 ? 'warning' : 'critical'}
            loading={loading}
          />
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column */}
          <div className="lg:col-span-2 space-y-6">
            {cardOrder.left.map((cardId, index) => (
              <DraggableCard
                key={cardId}
                id={cardId}
                isEditMode={isEditMode}
                onMoveUp={() => moveCard('left', index, -1)}
                onMoveDown={() => moveCard('left', index, 1)}
                canMoveUp={index > 0}
                canMoveDown={index < cardOrder.left.length - 1}
                height={cardSizes[cardId]}
                onResize={handleCardResize}
              >
                {cardId === 'heatmap' && (
                  <ViolationHeatmap
                    onCellClick={handleCellClick}
                    loading={loading}
                    filterEnv={selectedEnv}
                  />
                )}
                {cardId === 'timeline' && (
                  <ValidationTimeline
                    onSelectRun={handleSelectRun}
                    loading={loading}
                    maxItems={10}
                    filterEnv={selectedEnv}
                  />
                )}
              </DraggableCard>
            ))}
          </div>

          {/* Right column */}
          <div className="space-y-6">
            {cardOrder.right.map((cardId, index) => (
              <DraggableCard
                key={cardId}
                id={cardId}
                isEditMode={isEditMode}
                onMoveUp={() => moveCard('right', index, -1)}
                onMoveDown={() => moveCard('right', index, 1)}
                canMoveUp={index > 0}
                canMoveDown={index < cardOrder.right.length - 1}
                height={cardSizes[cardId]}
                onResize={handleCardResize}
              >
                {cardId === 'drift' && (
                  <DriftStatusPanel
                    onViewDiff={handleViewDiff}
                    onRescan={handleRescan}
                    loading={loading}
                    filterEnv={selectedEnv}
                  />
                )}
                {cardId === 'activity' && (
                  <AgentActivityFeed
                    loading={loading}
                    maxItems={15}
                    filterEnv={selectedEnv}
                  />
                )}
              </DraggableCard>
            ))}
          </div>
        </div>

        {/* Health status footer */}
        {health && (
          <div className="mt-6 p-4 bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
            <div className="flex items-center gap-4 text-sm">
              <span className="text-surface-500 dark:text-surface-400">Service Status:</span>
              <span className={`flex items-center gap-2 ${health.healthy ? 'text-olive-600 dark:text-olive-400' : 'text-critical-600 dark:text-critical-400'}`}>
                <span className={`w-2 h-2 rounded-full ${health.healthy ? 'bg-olive-500' : 'bg-critical-500'}`} />
                {health.healthy ? 'Healthy' : 'Unhealthy'}
              </span>
              <span className="text-surface-400">|</span>
              <span className="text-surface-500 dark:text-surface-400">
                Registry: {health.registry_loaded ? 'Loaded' : 'Not loaded'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
