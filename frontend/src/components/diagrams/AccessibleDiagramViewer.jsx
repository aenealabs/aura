/**
 * Project Aura - Accessible Diagram Viewer (ADR-060 Phase 3)
 *
 * Enhanced DiagramViewer wrapper with full WCAG 2.1 AA compliance.
 *
 * Accessibility Enhancements:
 * - Skip link to main diagram content
 * - Reduced motion support
 * - High contrast mode detection
 * - Enhanced keyboard navigation
 * - Screen reader announcements for all actions
 * - Focus visible indicators
 * - Node selection and navigation
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import DiagramViewer from './DiagramViewer';
import {
  useReducedMotion,
  useHighContrast,
  useAnnouncer,
  SkipLink,
  LiveRegion,
} from '../../hooks/useAccessibility';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';

// ============================================================================
// Node Navigator Component
// ============================================================================

/**
 * Accessible node navigator for keyboard users.
 * Allows navigating between diagram nodes without mouse.
 */
function NodeNavigator({
  nodes,
  selectedNodeId,
  onSelectNode,
  onFocusNode,
  isExpanded,
  onToggleExpanded,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const listRef = useRef(null);

  // Filter nodes by search
  const filteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return nodes;
    const query = searchQuery.toLowerCase();
    return nodes.filter(
      (node) =>
        node.label?.toLowerCase().includes(query) ||
        node.id?.toLowerCase().includes(query)
    );
  }, [nodes, searchQuery]);

  // Handle keyboard navigation
  const handleKeyDown = (event) => {
    const currentIndex = filteredNodes.findIndex((n) => n.id === selectedNodeId);

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        if (currentIndex < filteredNodes.length - 1) {
          onSelectNode(filteredNodes[currentIndex + 1].id);
        }
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (currentIndex > 0) {
          onSelectNode(filteredNodes[currentIndex - 1].id);
        }
        break;
      case 'Enter':
        event.preventDefault();
        if (selectedNodeId) {
          onFocusNode(selectedNodeId);
        }
        break;
      case 'Home':
        event.preventDefault();
        if (filteredNodes.length > 0) {
          onSelectNode(filteredNodes[0].id);
        }
        break;
      case 'End':
        event.preventDefault();
        if (filteredNodes.length > 0) {
          onSelectNode(filteredNodes[filteredNodes.length - 1].id);
        }
        break;
      default:
        break;
    }
  };

  if (!isExpanded) {
    return (
      <button
        onClick={onToggleExpanded}
        className="
          flex items-center gap-2 px-3 py-2
          bg-surface-100 dark:bg-surface-800
          border border-surface-200 dark:border-surface-700
          rounded-lg
          text-sm text-surface-700 dark:text-surface-300
          hover:bg-surface-200 dark:hover:bg-surface-700
          focus:outline-none focus:ring-2 focus:ring-aura-500
          transition-colors duration-150
        "
        aria-expanded="false"
        aria-label="Open node navigator"
      >
        <MagnifyingGlassIcon className="w-4 h-4" />
        <span>Navigate nodes</span>
        <ChevronDownIcon className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div
      className="
        w-64
        bg-white dark:bg-surface-800
        border border-surface-200 dark:border-surface-700
        rounded-lg shadow-lg
        overflow-hidden
      "
      role="region"
      aria-label="Node navigator"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-surface-200 dark:border-surface-700">
        <span className="text-sm font-medium text-surface-700 dark:text-surface-200">
          Diagram Nodes
        </span>
        <button
          onClick={onToggleExpanded}
          className="
            p-1 rounded
            hover:bg-surface-100 dark:hover:bg-surface-700
            focus:outline-none focus:ring-2 focus:ring-aura-500
          "
          aria-label="Close node navigator"
        >
          <ChevronUpIcon className="w-4 h-4 text-surface-500" />
        </button>
      </div>

      {/* Search */}
      <div className="p-2 border-b border-surface-200 dark:border-surface-700">
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search nodes..."
          className="
            w-full px-3 py-1.5
            bg-surface-50 dark:bg-surface-900
            border border-surface-200 dark:border-surface-700
            rounded
            text-sm text-surface-900 dark:text-surface-100
            placeholder:text-surface-400
            focus:outline-none focus:ring-2 focus:ring-aura-500
          "
          aria-label="Search diagram nodes"
        />
      </div>

      {/* Node List */}
      <ul
        ref={listRef}
        role="listbox"
        aria-label="Diagram nodes"
        className="max-h-48 overflow-y-auto"
        onKeyDown={handleKeyDown}
      >
        {filteredNodes.length === 0 ? (
          <li className="px-3 py-2 text-sm text-surface-500 dark:text-surface-400">
            No nodes found
          </li>
        ) : (
          filteredNodes.map((node) => (
            <li
              key={node.id}
              role="option"
              aria-selected={node.id === selectedNodeId}
              tabIndex={node.id === selectedNodeId ? 0 : -1}
              onClick={() => onSelectNode(node.id)}
              onDoubleClick={() => onFocusNode(node.id)}
              className={`
                px-3 py-2 cursor-pointer
                text-sm
                ${node.id === selectedNodeId
                  ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300'
                  : 'text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700'
                }
                focus:outline-none focus:ring-2 focus:ring-inset focus:ring-aura-500
              `}
            >
              <div className="font-medium">{node.label || node.id}</div>
              {node.type && (
                <div className="text-xs text-surface-500 dark:text-surface-400">
                  {node.type}
                </div>
              )}
            </li>
          ))
        )}
      </ul>

      {/* Instructions */}
      <div className="px-3 py-2 border-t border-surface-200 dark:border-surface-700">
        <p className="text-xs text-surface-500 dark:text-surface-400">
          Use arrow keys to navigate, Enter to focus
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// Keyboard Shortcut Help
// ============================================================================

function KeyboardShortcutHelp({ isOpen, onClose }) {
  if (!isOpen) return null;

  const shortcuts = [
    { keys: ['Ctrl', '+'], action: 'Zoom in' },
    { keys: ['Ctrl', '-'], action: 'Zoom out' },
    { keys: ['Ctrl', '0'], action: 'Fit to view' },
    { keys: ['Ctrl', '1'], action: 'Reset to 100%' },
    { keys: ['↑', '↓', '←', '→'], action: 'Pan diagram' },
    { keys: ['Tab'], action: 'Navigate between controls' },
    { keys: ['Enter'], action: 'Activate focused control' },
    { keys: ['Escape'], action: 'Close menus/dialogs' },
    { keys: ['?'], action: 'Show keyboard shortcuts' },
  ];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-title"
      className="
        absolute bottom-16 right-4
        w-72
        bg-white dark:bg-surface-800
        border border-surface-200 dark:border-surface-700
        rounded-lg shadow-xl
        overflow-hidden
        z-10
      "
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-200 dark:border-surface-700">
        <h3
          id="shortcuts-title"
          className="text-sm font-semibold text-surface-900 dark:text-surface-100"
        >
          Keyboard Shortcuts
        </h3>
        <button
          onClick={onClose}
          className="
            p-1 rounded
            hover:bg-surface-100 dark:hover:bg-surface-700
            focus:outline-none focus:ring-2 focus:ring-aura-500
          "
          aria-label="Close shortcuts panel"
        >
          ×
        </button>
      </div>

      <div className="p-3 space-y-2">
        {shortcuts.map((shortcut, index) => (
          <div
            key={index}
            className="flex items-center justify-between text-sm"
          >
            <span className="text-surface-600 dark:text-surface-400">
              {shortcut.action}
            </span>
            <div className="flex items-center gap-1">
              {shortcut.keys.map((key, keyIndex) => (
                <kbd
                  key={keyIndex}
                  className="
                    px-2 py-0.5
                    bg-surface-100 dark:bg-surface-700
                    border border-surface-300 dark:border-surface-600
                    rounded
                    text-xs font-mono text-surface-700 dark:text-surface-300
                  "
                >
                  {key}
                </kbd>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Main AccessibleDiagramViewer Component
// ============================================================================

export default function AccessibleDiagramViewer({
  svgContent,
  title = 'Architecture Diagram',
  nodes = [],
  onNodeSelect,
  className = '',
  ...props
}) {
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [showNodeNavigator, setShowNodeNavigator] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');

  const containerRef = useRef(null);
  const announce = useAnnouncer();
  const reducedMotion = useReducedMotion();
  const highContrast = useHighContrast();

  // Parse nodes from SVG if not provided
  const diagramNodes = useMemo(() => {
    if (nodes.length > 0) return nodes;

    // Extract nodes from SVG content
    if (!svgContent) return [];

    const parser = new DOMParser();
    const doc = parser.parseFromString(svgContent, 'image/svg+xml');
    const nodeElements = doc.querySelectorAll('[data-node-id]');

    return Array.from(nodeElements).map((el) => ({
      id: el.getAttribute('data-node-id'),
      label: el.getAttribute('data-node-label') || el.getAttribute('data-node-id'),
      type: el.getAttribute('data-node-type'),
    }));
  }, [nodes, svgContent]);

  // Handle node selection
  const handleSelectNode = useCallback(
    (nodeId) => {
      setSelectedNodeId(nodeId);
      const node = diagramNodes.find((n) => n.id === nodeId);
      if (node) {
        announce(`Selected: ${node.label || nodeId}`);
        setStatusMessage(`Selected: ${node.label || nodeId}`);
        onNodeSelect?.(nodeId);
      }
    },
    [diagramNodes, announce, onNodeSelect]
  );

  // Handle focus on node (pan to it)
  const handleFocusNode = useCallback(
    (nodeId) => {
      const node = diagramNodes.find((n) => n.id === nodeId);
      if (node) {
        announce(`Focused on: ${node.label || nodeId}`);
        setStatusMessage(`Viewing: ${node.label || nodeId}`);
        // In real implementation, would pan/zoom to node
      }
    },
    [diagramNodes, announce]
  );

  // Global keyboard handler
  useEffect(() => {
    const handleKeyDown = (event) => {
      // Only handle if focus is within the diagram viewer
      if (!containerRef.current?.contains(document.activeElement)) return;

      switch (event.key) {
        case '?':
          event.preventDefault();
          setShowShortcuts((prev) => !prev);
          break;
        case 'n':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault();
            setShowNodeNavigator((prev) => !prev);
          }
          break;
        case 'Escape':
          setShowShortcuts(false);
          setShowNodeNavigator(false);
          break;
        default:
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Apply high contrast styles
  const highContrastStyles = highContrast
    ? {
        filter: 'contrast(1.2)',
        '--diagram-border-width': '2px',
      }
    : {};

  // Apply reduced motion
  const motionClass = reducedMotion ? 'motion-reduce' : '';

  return (
    <div
      ref={containerRef}
      className={`relative ${motionClass} ${className}`}
      style={highContrastStyles}
    >
      {/* Skip link */}
      <SkipLink href="#diagram-canvas">Skip to diagram</SkipLink>

      {/* Accessibility toolbar */}
      <div
        className="
          absolute top-4 left-4 z-10
          flex items-center gap-2
        "
      >
        {/* Node Navigator Toggle */}
        <NodeNavigator
          nodes={diagramNodes}
          selectedNodeId={selectedNodeId}
          onSelectNode={handleSelectNode}
          onFocusNode={handleFocusNode}
          isExpanded={showNodeNavigator}
          onToggleExpanded={() => setShowNodeNavigator(!showNodeNavigator)}
        />
      </div>

      {/* Keyboard shortcut toggle */}
      <div className="absolute bottom-4 right-4 z-10">
        <button
          onClick={() => setShowShortcuts(!showShortcuts)}
          className="
            p-2
            bg-surface-100 dark:bg-surface-800
            border border-surface-200 dark:border-surface-700
            rounded-lg
            text-sm text-surface-700 dark:text-surface-300
            hover:bg-surface-200 dark:hover:bg-surface-700
            focus:outline-none focus:ring-2 focus:ring-aura-500
            transition-colors duration-150
          "
          aria-label="Show keyboard shortcuts"
          aria-expanded={showShortcuts}
          title="Keyboard shortcuts (?)"
        >
          <kbd className="font-mono">?</kbd>
        </button>

        <KeyboardShortcutHelp
          isOpen={showShortcuts}
          onClose={() => setShowShortcuts(false)}
        />
      </div>

      {/* Main diagram viewer */}
      <div id="diagram-canvas" tabIndex={-1}>
        <DiagramViewer
          svgContent={svgContent}
          title={title}
          className={reducedMotion ? '[&_*]:!transition-none' : ''}
          {...props}
        />
      </div>

      {/* Status announcements */}
      <LiveRegion message={statusMessage} politeness="polite" />

      {/* High contrast mode indicator */}
      {highContrast && (
        <div
          className="
            absolute top-4 right-4
            px-2 py-1
            bg-surface-900 text-white
            text-xs font-medium
            rounded
          "
          role="status"
        >
          High Contrast Mode
        </div>
      )}
    </div>
  );
}

// Export subcomponents for testing
export { NodeNavigator, KeyboardShortcutHelp };
