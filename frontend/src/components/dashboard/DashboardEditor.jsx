/**
 * Dashboard Editor Component
 *
 * Provides drag-and-drop dashboard customization with react-grid-layout.
 * Implements ADR-064 customizable dashboard widgets.
 */

import { useState, useCallback, useMemo, memo } from 'react';
import GridLayout from 'react-grid-layout';
import {
  PlusIcon,
  Cog6ToothIcon,
  TrashIcon,
  ArrowsPointingOutIcon,
  CheckIcon,
  XMarkIcon,
  Squares2X2Icon,
  ShareIcon,
  DocumentDuplicateIcon,
  EllipsisVerticalIcon,
} from '@heroicons/react/24/outline';

import 'react-grid-layout/css/styles.css';

import DashboardMetricCard from './MetricCard';
import WidgetLibrary from './WidgetLibrary';
import ShareDashboardModal from './ShareDashboardModal';
import { getWidgetById, WIDGET_CATALOG } from './widgetRegistry';

// Grid configuration
const GRID_COLS = 12;
const GRID_ROW_HEIGHT = 100;
const GRID_MARGIN = [16, 16];

// Widget placeholder component for rendering
const WidgetPlaceholder = memo(function WidgetPlaceholder({
  widget,
  definition,
  isEditMode,
  onRemove,
  onConfigure,
}) {
  if (!definition) {
    return (
      <div className="h-full flex items-center justify-center bg-surface-100 dark:bg-surface-800 rounded-xl border border-dashed border-surface-300 dark:border-surface-600">
        <span className="text-surface-500">Unknown widget</span>
      </div>
    );
  }

  return (
    <div className="h-full relative group">
      {/* Edit mode controls */}
      {isEditMode && (
        <div className="absolute top-2 right-2 z-10 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onConfigure(widget);
            }}
            className="p-1.5 rounded-lg bg-surface-100 dark:bg-surface-700 hover:bg-surface-200 dark:hover:bg-surface-600 text-surface-500 dark:text-surface-400"
            title="Configure widget"
          >
            <Cog6ToothIcon className="w-4 h-4" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove(widget.i);
            }}
            className="p-1.5 rounded-lg bg-critical-100 dark:bg-critical-900/30 hover:bg-critical-200 dark:hover:bg-critical-900/50 text-critical-600 dark:text-critical-400"
            title="Remove widget"
          >
            <TrashIcon className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Widget content */}
      <DashboardMetricCard
        title={definition.name}
        value="--"
        subtitle={definition.description}
        iconColor={widget.color || definition.defaultColor}
        loading={false}
      />
    </div>
  );
});

// Main Dashboard Editor component
export default function DashboardEditor({
  dashboard = null,
  initialLayout = [],
  initialWidgets = [],
  onSave,
  onCancel,
  onShare,
  onRevokeShare,
  onClone,
  existingShares = [],
  className = '',
}) {
  const [layout, setLayout] = useState(initialLayout);
  const [widgets, setWidgets] = useState(initialWidgets);
  const [isEditMode, setIsEditMode] = useState(false);
  const [showWidgetLibrary, setShowWidgetLibrary] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [selectedWidget, setSelectedWidget] = useState(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [isCloning, setIsCloning] = useState(false);

  // Handle clone dashboard
  const handleClone = useCallback(async () => {
    if (!onClone || !dashboard) return;

    setIsCloning(true);
    try {
      await onClone(dashboard.dashboard_id);
      setShowMenu(false);
    } catch (err) {
      console.error('Failed to clone dashboard:', err);
    } finally {
      setIsCloning(false);
    }
  }, [onClone, dashboard]);

  // Handle layout changes from drag/resize
  const handleLayoutChange = useCallback((newLayout) => {
    setLayout(newLayout);
    setHasChanges(true);
  }, []);

  // Add widget from library
  const handleAddWidget = useCallback((widgetDefinition) => {
    const widgetId = `widget-${widgetDefinition.id}-${Date.now()}`;

    // Find first available position
    const maxY = layout.reduce((max, item) => Math.max(max, item.y + item.h), 0);

    const newLayoutItem = {
      i: widgetId,
      x: 0,
      y: maxY,
      w: widgetDefinition.defaultWidth,
      h: widgetDefinition.defaultHeight,
      minW: widgetDefinition.minWidth,
      minH: widgetDefinition.minHeight,
    };

    const newWidget = {
      i: widgetId,
      definitionId: widgetDefinition.id,
      color: widgetDefinition.defaultColor,
      dataSource: widgetDefinition.dataSource,
      refreshSeconds: widgetDefinition.defaultRefreshSeconds,
    };

    setLayout((prev) => [...prev, newLayoutItem]);
    setWidgets((prev) => [...prev, newWidget]);
    setHasChanges(true);
    setShowWidgetLibrary(false);
  }, [layout]);

  // Remove widget
  const handleRemoveWidget = useCallback((widgetId) => {
    setLayout((prev) => prev.filter((item) => item.i !== widgetId));
    setWidgets((prev) => prev.filter((w) => w.i !== widgetId));
    setHasChanges(true);
  }, []);

  // Configure widget
  const handleConfigureWidget = useCallback((widget) => {
    setSelectedWidget(widget);
    // TODO: Open configuration modal
  }, []);

  // Save dashboard
  const handleSave = useCallback(() => {
    if (onSave) {
      onSave({
        layout,
        widgets,
      });
    }
    setHasChanges(false);
    setIsEditMode(false);
  }, [layout, widgets, onSave]);

  // Cancel edit
  const handleCancel = useCallback(() => {
    setLayout(initialLayout);
    setWidgets(initialWidgets);
    setHasChanges(false);
    setIsEditMode(false);
    if (onCancel) {
      onCancel();
    }
  }, [initialLayout, initialWidgets, onCancel]);

  // Get widget definition by widget data
  const getDefinition = useCallback((widget) => {
    return getWidgetById(widget.definitionId);
  }, []);

  // Memoize rendered widgets
  const renderedWidgets = useMemo(() => {
    return widgets.map((widget) => {
      const definition = getDefinition(widget);
      return (
        <div key={widget.i} className="dashboard-widget">
          <WidgetPlaceholder
            widget={widget}
            definition={definition}
            isEditMode={isEditMode}
            onRemove={handleRemoveWidget}
            onConfigure={handleConfigureWidget}
          />
        </div>
      );
    });
  }, [widgets, isEditMode, getDefinition, handleRemoveWidget, handleConfigureWidget]);

  return (
    <div className={`dashboard-editor ${className}`}>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 px-1">
        <div className="flex items-center gap-2">
          <Squares2X2Icon className="w-5 h-5 text-surface-500" />
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Dashboard
          </h2>
          {hasChanges && (
            <span className="text-xs text-warning-600 dark:text-warning-400 ml-2">
              (unsaved changes)
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isEditMode ? (
            <>
              <button
                onClick={() => setShowWidgetLibrary(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-aura-600 dark:text-aura-400 hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded-lg transition-colors"
              >
                <PlusIcon className="w-4 h-4" />
                Add Widget
              </button>
              <button
                onClick={handleCancel}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              >
                <XMarkIcon className="w-4 h-4" />
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!hasChanges}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                <CheckIcon className="w-4 h-4" />
                Save
              </button>
            </>
          ) : (
            <>
              {/* Share button */}
              {onShare && dashboard && (
                <button
                  onClick={() => setShowShareModal(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
                  title="Share dashboard"
                >
                  <ShareIcon className="w-4 h-4" />
                  Share
                </button>
              )}

              {/* Clone button */}
              {onClone && dashboard && (
                <button
                  onClick={handleClone}
                  disabled={isCloning}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 disabled:opacity-50 rounded-lg transition-colors"
                  title="Clone dashboard"
                >
                  <DocumentDuplicateIcon className="w-4 h-4" />
                  {isCloning ? 'Cloning...' : 'Clone'}
                </button>
              )}

              {/* Edit button */}
              <button
                onClick={() => setIsEditMode(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              >
                <ArrowsPointingOutIcon className="w-4 h-4" />
                Edit Layout
              </button>
            </>
          )}
        </div>
      </div>

      {/* Grid Layout */}
      <div
        className={`
          dashboard-grid
          ${isEditMode ? 'edit-mode bg-surface-50 dark:bg-surface-900/50 rounded-xl p-4' : ''}
        `}
      >
        {widgets.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Squares2X2Icon className="w-12 h-12 text-surface-300 dark:text-surface-600 mb-4" />
            <h3 className="text-lg font-medium text-surface-700 dark:text-surface-300 mb-2">
              No widgets yet
            </h3>
            <p className="text-sm text-surface-500 dark:text-surface-400 mb-4">
              Click &quot;Edit Layout&quot; to add widgets to your dashboard
            </p>
            {!isEditMode && (
              <button
                onClick={() => setIsEditMode(true)}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 rounded-lg transition-colors"
              >
                <PlusIcon className="w-4 h-4" />
                Get Started
              </button>
            )}
          </div>
        ) : (
          <GridLayout
            className="layout"
            layout={layout}
            cols={GRID_COLS}
            rowHeight={GRID_ROW_HEIGHT}
            margin={GRID_MARGIN}
            isDraggable={isEditMode}
            isResizable={isEditMode}
            onLayoutChange={handleLayoutChange}
            draggableHandle=".dashboard-widget"
            useCSSTransforms={true}
          >
            {renderedWidgets}
          </GridLayout>
        )}
      </div>

      {/* Widget Library Slide-over */}
      {showWidgetLibrary && (
        <WidgetLibrary
          onSelect={handleAddWidget}
          onClose={() => setShowWidgetLibrary(false)}
        />
      )}

      {/* Share Dashboard Modal */}
      {showShareModal && dashboard && (
        <ShareDashboardModal
          dashboard={dashboard}
          isOpen={showShareModal}
          onClose={() => setShowShareModal(false)}
          onShare={onShare}
          onRevoke={onRevokeShare}
          existingShares={existingShares}
        />
      )}
    </div>
  );
}
