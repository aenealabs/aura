/**
 * Widget Library Component
 *
 * Slide-over panel displaying categorized widgets for selection.
 * Implements ADR-064 widget catalog UI.
 */

import { useState, useMemo, memo } from 'react';
import {
  XMarkIcon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ShieldCheckIcon,
  CogIcon,
  ChartBarIcon,
  ClipboardDocumentCheckIcon,
  CurrencyDollarIcon,
} from '@heroicons/react/24/outline';

import {
  getCategorizedWidgets,
  WidgetCategory,
  CATEGORY_LABELS,
} from './widgetRegistry';

// Category icons
const CATEGORY_ICONS = {
  [WidgetCategory.SECURITY]: ShieldCheckIcon,
  [WidgetCategory.OPERATIONS]: CogIcon,
  [WidgetCategory.ANALYTICS]: ChartBarIcon,
  [WidgetCategory.COMPLIANCE]: ClipboardDocumentCheckIcon,
  [WidgetCategory.COST]: CurrencyDollarIcon,
};

// Widget preview card
const WidgetPreviewCard = memo(function WidgetPreviewCard({
  widget,
  onSelect,
  isSelected,
}) {
  return (
    <button
      onClick={() => onSelect(widget)}
      className={`
        w-full text-left p-3 rounded-lg border transition-all duration-200
        ${isSelected
          ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20 ring-2 ring-aura-500/20'
          : 'border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-700 hover:bg-surface-50 dark:hover:bg-surface-800'
        }
      `}
    >
      <div className="flex items-start gap-3">
        <div
          className={`
            w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0
            ${getColorClass(widget.defaultColor)}
          `}
        >
          <span className="text-lg font-bold">
            {widget.name.charAt(0)}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
            {widget.name}
          </h4>
          <p className="text-xs text-surface-500 dark:text-surface-400 line-clamp-2 mt-0.5">
            {widget.description}
          </p>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xs text-surface-400 dark:text-surface-500">
              {widget.defaultWidth}x{widget.defaultHeight}
            </span>
            {widget.supportsSparkline && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400">
                Sparkline
              </span>
            )}
            {widget.supportsTrend && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400">
                Trend
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  );
});

// Category accordion
const CategoryAccordion = memo(function CategoryAccordion({
  category,
  label,
  widgets,
  isExpanded,
  onToggle,
  onSelectWidget,
  selectedWidget,
}) {
  const Icon = CATEGORY_ICONS[category] || ChartBarIcon;

  return (
    <div className="border-b border-surface-200 dark:border-surface-700 last:border-b-0">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface-50 dark:hover:bg-surface-800 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-5 h-5 text-surface-500" />
          <span className="font-medium text-surface-900 dark:text-surface-100">
            {label}
          </span>
          <span className="text-xs text-surface-400 dark:text-surface-500 ml-1">
            ({widgets.length})
          </span>
        </div>
        {isExpanded ? (
          <ChevronDownIcon className="w-5 h-5 text-surface-400" />
        ) : (
          <ChevronRightIcon className="w-5 h-5 text-surface-400" />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 space-y-2">
          {widgets.map((widget) => (
            <WidgetPreviewCard
              key={widget.id}
              widget={widget}
              onSelect={onSelectWidget}
              isSelected={selectedWidget?.id === widget.id}
            />
          ))}
        </div>
      )}
    </div>
  );
});

// Helper function to get Tailwind color classes
function getColorClass(color) {
  const colorMap = {
    aura: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
    olive: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
    critical: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
    warning: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
    surface: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-300',
  };
  return colorMap[color] || colorMap.aura;
}

// Main Widget Library component
export default function WidgetLibrary({ onSelect, onClose }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCategories, setExpandedCategories] = useState(
    new Set([WidgetCategory.SECURITY])
  );
  const [selectedWidget, setSelectedWidget] = useState(null);

  // Get categorized widgets
  const categorizedWidgets = useMemo(() => getCategorizedWidgets(), []);

  // Filter widgets by search query
  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) {
      return categorizedWidgets;
    }

    const query = searchQuery.toLowerCase();
    return categorizedWidgets
      .map((cat) => ({
        ...cat,
        widgets: cat.widgets.filter(
          (w) =>
            w.name.toLowerCase().includes(query) ||
            w.description.toLowerCase().includes(query)
        ),
      }))
      .filter((cat) => cat.widgets.length > 0);
  }, [categorizedWidgets, searchQuery]);

  // Toggle category expansion
  const toggleCategory = (category) => {
    setExpandedCategories((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(category)) {
        newSet.delete(category);
      } else {
        newSet.add(category);
      }
      return newSet;
    });
  };

  // Handle widget selection
  const handleSelectWidget = (widget) => {
    setSelectedWidget(widget);
  };

  // Handle add to dashboard
  const handleAddToDashboard = () => {
    if (selectedWidget && onSelect) {
      onSelect(selectedWidget);
      setSelectedWidget(null);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div className="fixed inset-y-0 right-0 w-full max-w-md bg-white dark:bg-surface-900 shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-surface-200 dark:border-surface-700">
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Widget Library
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-500 transition-colors"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-3 border-b border-surface-200 dark:border-surface-700">
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
            <input
              type="text"
              placeholder="Search widgets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="
                w-full pl-10 pr-4 py-2 rounded-lg
                bg-surface-50 dark:bg-surface-800
                border border-surface-200 dark:border-surface-700
                text-surface-900 dark:text-surface-100
                placeholder-surface-400
                focus:outline-none focus:ring-2 focus:ring-aura-500/20 focus:border-aura-500
                transition-colors
              "
            />
          </div>
        </div>

        {/* Widget categories */}
        <div className="flex-1 overflow-y-auto">
          {filteredCategories.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
              <MagnifyingGlassIcon className="w-10 h-10 text-surface-300 dark:text-surface-600 mb-3" />
              <p className="text-surface-500 dark:text-surface-400">
                No widgets found for &quot;{searchQuery}&quot;
              </p>
            </div>
          ) : (
            filteredCategories.map((cat) => (
              <CategoryAccordion
                key={cat.category}
                category={cat.category}
                label={cat.label}
                widgets={cat.widgets}
                isExpanded={expandedCategories.has(cat.category)}
                onToggle={() => toggleCategory(cat.category)}
                onSelectWidget={handleSelectWidget}
                selectedWidget={selectedWidget}
              />
            ))
          )}
        </div>

        {/* Footer with action buttons */}
        <div className="px-4 py-3 border-t border-surface-200 dark:border-surface-700 flex items-center justify-between gap-3">
          {selectedWidget ? (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                {selectedWidget.name}
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                {selectedWidget.defaultWidth}x{selectedWidget.defaultHeight} • {CATEGORY_LABELS[selectedWidget.category]}
              </p>
            </div>
          ) : (
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Select a widget to add
            </p>
          )}
          <button
            onClick={handleAddToDashboard}
            disabled={!selectedWidget}
            className="
              px-4 py-2 rounded-lg font-medium text-sm
              bg-aura-600 hover:bg-aura-700 text-white
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors
            "
          >
            Add to Dashboard
          </button>
        </div>
      </div>
    </>
  );
}
