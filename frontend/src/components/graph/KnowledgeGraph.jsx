/**
 * Project Aura - Knowledge Graph Visualization Component
 *
 * Interactive graph visualization for code entities with file navigation.
 * Features include node clicking, relationship expansion, and context menus.
 *
 * Uses D3.js-inspired force simulation for graph layout.
 *
 * Design System: Apple-inspired with clean typography, generous spacing,
 * and smooth transitions per design-principles.md
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import {
  DocumentIcon,
  CodeBracketIcon,
  CubeIcon,
  VariableIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  MagnifyingGlassIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon,
  DocumentDuplicateIcon,
  EyeIcon,
  LinkIcon,
  ArrowTopRightOnSquareIcon,
  AdjustmentsHorizontalIcon,
} from '@heroicons/react/24/outline';
import FileViewer from './FileViewer';

// ============================================================================
// Constants & Configuration
// ============================================================================

const NODE_TYPES = {
  file: {
    icon: DocumentIcon,
    color: '#3B82F6', // aura blue
    radius: 24,
  },
  class: {
    icon: CubeIcon,
    color: '#8B5CF6', // purple
    radius: 20,
  },
  function: {
    icon: CodeBracketIcon,
    color: '#10B981', // olive green
    radius: 16,
  },
  variable: {
    icon: VariableIcon,
    color: '#F59E0B', // warning amber
    radius: 12,
  },
  module: {
    icon: DocumentIcon,
    color: '#6366F1', // indigo
    radius: 22,
  },
};

const EDGE_TYPES = {
  imports: { color: '#94A3B8', dashed: false },
  calls: { color: '#10B981', dashed: false },
  extends: { color: '#8B5CF6', dashed: true },
  uses: { color: '#F59E0B', dashed: true },
  contains: { color: '#CBD5E1', dashed: false },
};

// ============================================================================
// Force Simulation (D3-inspired)
// ============================================================================

function createForceSimulation(nodes, edges, width, height) {
  // Initialize node positions
  nodes.forEach((node, _i) => {
    if (node.x === undefined) {
      node.x = width / 2 + (Math.random() - 0.5) * 200;
      node.y = height / 2 + (Math.random() - 0.5) * 200;
    }
    node.vx = 0;
    node.vy = 0;
  });

  // Simulation parameters
  const alpha = 0.3;
  const _alphaDecay = 0.02;
  const velocityDecay = 0.6;
  const linkDistance = 100;
  const linkStrength = 0.5;
  const chargeStrength = -300;
  const centerStrength = 0.05;

  function tick() {
    // Apply forces
    nodes.forEach((node) => {
      // Center force
      node.vx += (width / 2 - node.x) * centerStrength * alpha;
      node.vy += (height / 2 - node.y) * centerStrength * alpha;

      // Charge force (repulsion between nodes)
      nodes.forEach((other) => {
        if (node.id === other.id) return;
        const dx = other.x - node.x;
        const dy = other.y - node.y;
        const distance = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (chargeStrength * alpha) / (distance * distance);
        node.vx -= (dx / distance) * force;
        node.vy -= (dy / distance) * force;
      });
    });

    // Link force
    edges.forEach((edge) => {
      const source = nodes.find((n) => n.id === edge.source);
      const target = nodes.find((n) => n.id === edge.target);
      if (!source || !target) return;

      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = ((distance - linkDistance) * linkStrength * alpha) / distance;

      source.vx += dx * force;
      source.vy += dy * force;
      target.vx -= dx * force;
      target.vy -= dy * force;
    });

    // Update positions
    nodes.forEach((node) => {
      node.vx *= velocityDecay;
      node.vy *= velocityDecay;
      node.x += node.vx;
      node.y += node.vy;

      // Keep within bounds
      const padding = 50;
      node.x = Math.max(padding, Math.min(width - padding, node.x));
      node.y = Math.max(padding, Math.min(height - padding, node.y));
    });

    return nodes;
  }

  return { tick };
}

// ============================================================================
// Context Menu Component
// ============================================================================

function ContextMenu({ x, y, node, onAction, onClose }) {
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  const menuItems = [
    { id: 'view-file', icon: EyeIcon, label: 'View File', action: 'viewFile' },
    { id: 'view-refs', icon: LinkIcon, label: 'View References', action: 'viewReferences' },
    { id: 'copy-path', icon: DocumentDuplicateIcon, label: 'Copy Path', action: 'copyPath' },
    { id: 'open-ide', icon: ArrowTopRightOnSquareIcon, label: 'Open in IDE', action: 'openInIDE' },
  ];

  // Adjust menu position to stay within viewport
  const adjustedX = Math.min(x, window.innerWidth - 200);
  const adjustedY = Math.min(y, window.innerHeight - 200);

  return createPortal(
    <div
      ref={menuRef}
      className="fixed z-50 bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-xl shadow-[var(--shadow-glass-hover)] border border-white/50 dark:border-surface-700/50 py-2 min-w-[180px] animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]"
      style={{ left: adjustedX, top: adjustedY }}
    >
      <div className="px-3 py-2 border-b border-surface-100/50 dark:border-surface-700/30">
        <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
          {node.label}
        </p>
        <p className="text-xs text-surface-500 dark:text-surface-400 capitalize">
          {node.type}
        </p>
      </div>

      <div className="py-1">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => {
              onAction(item.action, node);
              onClose();
            }}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            <item.icon className="w-4 h-4 text-surface-400" />
            {item.label}
          </button>
        ))}
      </div>
    </div>,
    document.body
  );
}

// ============================================================================
// Graph Node Component
// ============================================================================

function GraphNode({
  node,
  isSelected,
  isHovered,
  scale,
  onClick,
  onDoubleClick,
  onContextMenu,
  onMouseEnter,
  onMouseLeave,
}) {
  const config = NODE_TYPES[node.type] || NODE_TYPES.file;
  const Icon = config.icon;
  const radius = config.radius * (isHovered ? 1.1 : 1);

  return (
    <g
      transform={`translate(${node.x}, ${node.y})`}
      className="cursor-pointer transition-transform duration-150"
      onClick={(e) => onClick(e, node)}
      onDoubleClick={(e) => onDoubleClick(e, node)}
      onContextMenu={(e) => onContextMenu(e, node)}
      onMouseEnter={() => onMouseEnter(node)}
      onMouseLeave={() => onMouseLeave(node)}
    >
      {/* Selection ring */}
      {isSelected && (
        <circle
          r={radius + 6}
          fill="none"
          stroke="#3B82F6"
          strokeWidth="2"
          strokeDasharray="4 2"
          className="animate-pulse"
        />
      )}

      {/* Hover glow */}
      {isHovered && (
        <circle
          r={radius + 4}
          fill={config.color}
          opacity="0.2"
          className="transition-opacity"
        />
      )}

      {/* Main node circle */}
      <circle
        r={radius}
        fill="white"
        stroke={config.color}
        strokeWidth="2"
        className="drop-shadow-sm"
      />

      {/* Icon */}
      <foreignObject
        x={-radius * 0.6}
        y={-radius * 0.6}
        width={radius * 1.2}
        height={radius * 1.2}
      >
        <div className="w-full h-full flex items-center justify-center">
          <Icon
            className="w-1/2 h-1/2"
            style={{ color: config.color }}
          />
        </div>
      </foreignObject>

      {/* Label */}
      <text
        y={radius + 16}
        textAnchor="middle"
        className="text-xs font-medium fill-surface-700 dark:fill-surface-300 select-none"
        style={{ fontSize: Math.max(10, 12 / scale) }}
      >
        {node.label.length > 20 ? node.label.slice(0, 17) + '...' : node.label}
      </text>
    </g>
  );
}

// ============================================================================
// Graph Edge Component
// ============================================================================

function GraphEdge({ edge, sourceNode, targetNode, isHighlighted }) {
  if (!sourceNode || !targetNode) return null;

  const config = EDGE_TYPES[edge.type] || EDGE_TYPES.uses;

  // Calculate edge path
  const dx = targetNode.x - sourceNode.x;
  const dy = targetNode.y - sourceNode.y;
  const distance = Math.sqrt(dx * dx + dy * dy);

  if (distance < 1) return null;

  const sourceConfig = NODE_TYPES[sourceNode.type] || NODE_TYPES.file;
  const targetConfig = NODE_TYPES[targetNode.type] || NODE_TYPES.file;

  // Shorten edges to not overlap with nodes
  const startX = sourceNode.x + (dx / distance) * sourceConfig.radius;
  const startY = sourceNode.y + (dy / distance) * sourceConfig.radius;
  const endX = targetNode.x - (dx / distance) * (targetConfig.radius + 5);
  const endY = targetNode.y - (dy / distance) * (targetConfig.radius + 5);

  return (
    <g className="transition-opacity duration-150">
      <line
        x1={startX}
        y1={startY}
        x2={endX}
        y2={endY}
        stroke={isHighlighted ? '#3B82F6' : config.color}
        strokeWidth={isHighlighted ? 2 : 1.5}
        strokeDasharray={config.dashed ? '4 2' : undefined}
        markerEnd="url(#arrowhead)"
        opacity={isHighlighted ? 1 : 0.6}
      />
    </g>
  );
}

// ============================================================================
// Graph Controls Component
// ============================================================================

function GraphControls({ zoom, onZoomIn, onZoomOut, onToggleFullscreen, isFullscreen, onToggleSettings }) {
  return (
    <div className="absolute bottom-4 right-4 flex flex-col gap-1 bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-xl shadow-[var(--shadow-glass)] border border-white/50 dark:border-surface-700/50 p-1 z-10">
      <button
        onClick={onZoomIn}
        className="p-2 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
        aria-label="Zoom in"
      >
        <MagnifyingGlassPlusIcon className="w-5 h-5 text-surface-600 dark:text-surface-400" />
      </button>

      <div className="text-center text-xs text-surface-500 py-1">
        {Math.round(zoom * 100)}%
      </div>

      <button
        onClick={onZoomOut}
        className="p-2 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
        aria-label="Zoom out"
      >
        <MagnifyingGlassMinusIcon className="w-5 h-5 text-surface-600 dark:text-surface-400" />
      </button>

      <div className="border-t border-surface-100/50 dark:border-surface-700/30 my-1" />

      <button
        onClick={onToggleFullscreen}
        className="p-2 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
        aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
        title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
      >
        {isFullscreen ? (
          <ArrowsPointingInIcon className="w-5 h-5 text-surface-600 dark:text-surface-400" />
        ) : (
          <ArrowsPointingOutIcon className="w-5 h-5 text-surface-600 dark:text-surface-400" />
        )}
      </button>

      <button
        onClick={onToggleSettings}
        className="p-2 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
        aria-label="Graph settings"
      >
        <AdjustmentsHorizontalIcon className="w-5 h-5 text-surface-600 dark:text-surface-400" />
      </button>
    </div>
  );
}

// ============================================================================
// Mini Map Component
// ============================================================================

function MiniMap({ nodes, edges, viewBox, containerSize, _onViewportChange }) {
  const mapWidth = 150;
  const mapHeight = 100;

  // Calculate bounds
  const xMin = Math.min(...nodes.map((n) => n.x)) - 50;
  const xMax = Math.max(...nodes.map((n) => n.x)) + 50;
  const yMin = Math.min(...nodes.map((n) => n.y)) - 50;
  const yMax = Math.max(...nodes.map((n) => n.y)) + 50;
  const graphWidth = xMax - xMin;
  const graphHeight = yMax - yMin;

  // Scale to fit minimap
  const scaleX = mapWidth / graphWidth;
  const scaleY = mapHeight / graphHeight;
  const scale = Math.min(scaleX, scaleY, 1);

  return (
    <div className="absolute bottom-4 left-4 bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-xl shadow-[var(--shadow-glass)] border border-white/50 dark:border-surface-700/50 overflow-hidden">
      <svg width={mapWidth} height={mapHeight} className="bg-surface-50/50 dark:bg-surface-900/50">
        <g transform={`translate(${(mapWidth - graphWidth * scale) / 2}, ${(mapHeight - graphHeight * scale) / 2}) scale(${scale})`}>
          {/* Edges */}
          {edges.map((edge) => {
            const source = nodes.find((n) => n.id === edge.source);
            const target = nodes.find((n) => n.id === edge.target);
            if (!source || !target) return null;
            return (
              <line
                key={edge.id}
                x1={source.x - xMin}
                y1={source.y - yMin}
                x2={target.x - xMin}
                y2={target.y - yMin}
                stroke="#CBD5E1"
                strokeWidth={1 / scale}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const config = NODE_TYPES[node.type] || NODE_TYPES.file;
            return (
              <circle
                key={node.id}
                cx={node.x - xMin}
                cy={node.y - yMin}
                r={4 / scale}
                fill={config.color}
              />
            );
          })}

          {/* Viewport indicator */}
          <rect
            x={(viewBox.x - xMin)}
            y={(viewBox.y - yMin)}
            width={containerSize.width / viewBox.scale}
            height={containerSize.height / viewBox.scale}
            fill="none"
            stroke="#3B82F6"
            strokeWidth={2 / scale}
            rx={4 / scale}
          />
        </g>
      </svg>
    </div>
  );
}

// ============================================================================
// Main Knowledge Graph Component
// ============================================================================

export default function KnowledgeGraph({
  nodes: initialNodes = [],
  edges: initialEdges = [],
  _repositoryId = null,
  onNodeSelect,
  onFileOpen,
  className = '',
}) {
  // Graph data state
  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);

  // Interaction state
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragNode, setDragNode] = useState(null);

  // View state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [containerSize, setContainerSize] = useState({ width: 800, height: 600 });
  const [isFullscreen, setIsFullscreen] = useState(false);

  // File viewer state
  const [fileViewerOpen, setFileViewerOpen] = useState(false);
  const [fileViewerFile, setFileViewerFile] = useState(null);

  // Refs
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const simulationRef = useRef(null);

  // Initialize with mock data if no nodes provided
  useEffect(() => {
    if (initialNodes.length === 0) {
      // Generate mock graph data for demonstration
      const mockNodes = [
        { id: 'file-1', type: 'file', label: 'login.py', path: 'src/auth/handlers/login.py' },
        { id: 'file-2', type: 'file', label: 'users.js', path: 'src/api/routes/users.js' },
        { id: 'class-1', type: 'class', label: 'LoginRequest', path: 'src/auth/handlers/login.py', line: 23 },
        { id: 'class-2', type: 'class', label: 'LoginResponse', path: 'src/auth/handlers/login.py', line: 35 },
        { id: 'func-1', type: 'function', label: 'handle_login', path: 'src/auth/handlers/login.py', line: 45 },
        { id: 'func-2', type: 'function', label: 'authenticate', path: 'src/auth/services.py', line: 12 },
        { id: 'class-3', type: 'class', label: 'UserService', path: 'src/api/routes/users.js', line: 15 },
        { id: 'func-3', type: 'function', label: 'listUsers', path: 'src/api/routes/users.js', line: 38 },
        { id: 'func-4', type: 'function', label: 'createUser', path: 'src/api/routes/users.js', line: 82 },
        { id: 'module-1', type: 'module', label: 'auth_service', path: 'src/auth/services.py' },
      ];

      const mockEdges = [
        { id: 'e1', source: 'file-1', target: 'class-1', type: 'contains' },
        { id: 'e2', source: 'file-1', target: 'class-2', type: 'contains' },
        { id: 'e3', source: 'file-1', target: 'func-1', type: 'contains' },
        { id: 'e4', source: 'func-1', target: 'func-2', type: 'calls' },
        { id: 'e5', source: 'func-1', target: 'class-1', type: 'uses' },
        { id: 'e6', source: 'func-1', target: 'class-2', type: 'uses' },
        { id: 'e7', source: 'file-2', target: 'class-3', type: 'contains' },
        { id: 'e8', source: 'class-3', target: 'func-3', type: 'contains' },
        { id: 'e9', source: 'class-3', target: 'func-4', type: 'contains' },
        { id: 'e10', source: 'func-1', target: 'module-1', type: 'imports' },
        { id: 'e11', source: 'module-1', target: 'func-2', type: 'contains' },
      ];

      setNodes(mockNodes);
      setEdges(mockEdges);
    }
  }, [initialNodes]);

  // Handle container resize
  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Run force simulation
  useEffect(() => {
    if (nodes.length === 0) return;

    simulationRef.current = createForceSimulation(
      nodes,
      edges,
      containerSize.width,
      containerSize.height
    );

    let frameCount = 0;
    const maxFrames = 100;

    const animate = () => {
      if (frameCount >= maxFrames) return;

      simulationRef.current.tick();
      setNodes([...nodes]);
      frameCount++;

      requestAnimationFrame(animate);
    };

    animate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length, edges.length, containerSize]);

  // Handle node click
  const handleNodeClick = useCallback((e, node) => {
    e.stopPropagation();
    setSelectedNode(node.id === selectedNode ? null : node.id);
    onNodeSelect?.(node);
  }, [selectedNode, onNodeSelect]);

  // Handle node double-click (expand relationships)
  const handleNodeDoubleClick = useCallback((e, node) => {
    e.stopPropagation();

    // Open file in viewer
    if (node.path) {
      setFileViewerFile({ path: node.path, line: node.line });
      setFileViewerOpen(true);
      onFileOpen?.(node.path, node.line);
    }
  }, [onFileOpen]);

  // Handle context menu
  const handleContextMenu = useCallback((e, node) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      node,
    });
  }, []);

  // Handle context menu actions
  const handleContextMenuAction = useCallback((action, node) => {
    switch (action) {
      case 'viewFile':
        if (node.path) {
          setFileViewerFile({ path: node.path, line: node.line });
          setFileViewerOpen(true);
          onFileOpen?.(node.path, node.line);
        }
        break;
      case 'viewReferences':
        // TODO: Implement reference viewing
        break;
      case 'copyPath':
        if (node.path) {
          navigator.clipboard.writeText(node.path);
        }
        break;
      case 'openInIDE':
        // TODO: Implement IDE integration
        break;
      default:
        break;
    }
  }, [onFileOpen]);

  // Handle canvas pan
  const handleCanvasPan = useCallback((e) => {
    if (e.buttons !== 1 || dragNode) return;

    setPan((prev) => ({
      x: prev.x + e.movementX,
      y: prev.y + e.movementY,
    }));
  }, [dragNode]);

  // Handle node drag
  const handleNodeDrag = useCallback((e) => {
    if (!dragNode) return;

    setNodes((prev) =>
      prev.map((node) =>
        node.id === dragNode.id
          ? {
            ...node,
            x: node.x + e.movementX / zoom,
            y: node.y + e.movementY / zoom,
          }
          : node
      )
    );
  }, [dragNode, zoom]);

  // Handle zoom
  const handleWheel = useCallback((e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((prev) => Math.max(0.2, Math.min(3, prev * delta)));
  }, []);

  // Zoom controls
  const handleZoomIn = useCallback(() => {
    setZoom((prev) => Math.min(3, prev * 1.2));
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoom((prev) => Math.max(0.2, prev * 0.8));
  }, []);

  const handleFitView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  // Toggle fullscreen mode (CSS-based for reliability)
  const handleToggleFullscreen = useCallback(() => {
    setIsFullscreen(prev => !prev);
  }, []);

  // Handle Escape key to exit fullscreen
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);

  // Get highlighted edges (connected to selected or hovered node)
  const highlightedEdges = useMemo(() => {
    const activeNode = hoveredNode || selectedNode;
    if (!activeNode) return new Set();

    return new Set(
      edges
        .filter((e) => e.source === activeNode || e.target === activeNode)
        .map((e) => e.id)
    );
  }, [edges, hoveredNode, selectedNode]);

  // ViewBox for minimap
  const viewBox = {
    x: -pan.x / zoom,
    y: -pan.y / zoom,
    scale: zoom,
  };

  return (
    <div
      ref={containerRef}
      className={`relative flex h-full ${className} ${isFullscreen ? 'fixed inset-0 z-50 bg-surface-900' : ''}`}
      style={isFullscreen ? { width: '100vw', height: '100vh' } : undefined}
    >
      {/* Main graph area */}
      <div
        className={`flex-1 bg-surface-900 overflow-hidden ${fileViewerOpen && !isFullscreen ? 'w-1/2' : 'w-full'}`}
        onMouseMove={(e) => {
          if (isDragging) handleCanvasPan(e);
          if (dragNode) handleNodeDrag(e);
        }}
        onMouseUp={() => {
          setIsDragging(false);
          setDragNode(null);
        }}
        onMouseLeave={() => {
          setIsDragging(false);
          setDragNode(null);
        }}
      >
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          className="cursor-grab active:cursor-grabbing"
          onMouseDown={(e) => {
            if (e.target === svgRef.current || e.target.tagName === 'svg') {
              setIsDragging(true);
              setSelectedNode(null);
            }
          }}
          onWheel={handleWheel}
          onClick={() => {
            setContextMenu(null);
          }}
        >
          {/* Defs for markers */}
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon
                points="0 0, 10 3.5, 0 7"
                fill="#94A3B8"
              />
            </marker>
          </defs>

          {/* Transform group for pan and zoom */}
          <g transform={`translate(${pan.x + containerSize.width / 2}, ${pan.y + containerSize.height / 2}) scale(${zoom}) translate(${-containerSize.width / 2}, ${-containerSize.height / 2})`}>
            {/* Edges */}
            {edges.map((edge) => {
              const sourceNode = nodes.find((n) => n.id === edge.source);
              const targetNode = nodes.find((n) => n.id === edge.target);

              return (
                <GraphEdge
                  key={edge.id}
                  edge={edge}
                  sourceNode={sourceNode}
                  targetNode={targetNode}
                  isHighlighted={highlightedEdges.has(edge.id)}
                />
              );
            })}

            {/* Nodes */}
            {nodes.map((node) => (
              <GraphNode
                key={node.id}
                node={node}
                isSelected={selectedNode === node.id}
                isHovered={hoveredNode === node.id}
                scale={zoom}
                onClick={handleNodeClick}
                onDoubleClick={handleNodeDoubleClick}
                onContextMenu={handleContextMenu}
                onMouseEnter={(n) => setHoveredNode(n.id)}
                onMouseLeave={() => setHoveredNode(null)}
              />
            ))}
          </g>
        </svg>

        {/* Controls */}
        <GraphControls
          zoom={zoom}
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onToggleFullscreen={handleToggleFullscreen}
          isFullscreen={isFullscreen}
          onToggleSettings={() => {
            // TODO: Implement settings panel toggle
          }}
        />

        {/* Mini map */}
        {nodes.length > 0 && (
          <MiniMap
            nodes={nodes}
            edges={edges}
            viewBox={viewBox}
            containerSize={containerSize}
            onViewportChange={() => { }}
          />
        )}

        {/* Legend */}
        <div className="absolute top-4 left-4 bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-xl shadow-[var(--shadow-glass)] border border-white/50 dark:border-surface-700/50 p-3">
          <p className="text-xs font-medium text-surface-500 dark:text-surface-400 mb-2">
            Node Types
          </p>
          <div className="space-y-1.5">
            {Object.entries(NODE_TYPES).map(([type, config]) => (
              <div key={type} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: config.color }}
                />
                <span className="text-xs text-surface-700 dark:text-surface-300 capitalize">
                  {type}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Instructions */}
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-surface-400">
              <MagnifyingGlassIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p className="text-lg font-medium">No graph data</p>
              <p className="text-sm mt-1">Select a repository to visualize its code structure</p>
            </div>
          </div>
        )}
      </div>

      {/* File Viewer Panel */}
      {fileViewerOpen && (
        <div className="w-1/2 border-l border-surface-100/50 dark:border-surface-700/30">
          <FileViewer
            initialFile={fileViewerFile}
            highlightedLines={fileViewerFile?.line ? [fileViewerFile.line] : []}
            onClose={() => setFileViewerOpen(false)}
            onLineClick={(_line) => {
              // TODO: Handle line click - navigate to code reference
            }}
          />
        </div>
      )}

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          node={contextMenu.node}
          onAction={handleContextMenuAction}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}

// ============================================================================
// Exports
// ============================================================================

export { GraphNode, GraphEdge, GraphControls, MiniMap, ContextMenu, NODE_TYPES, EDGE_TYPES };
