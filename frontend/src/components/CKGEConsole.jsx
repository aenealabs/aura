import { useState, useEffect, useRef, useCallback } from 'react';
import {
  MagnifyingGlassIcon,
  ArrowPathIcon,
  AdjustmentsHorizontalIcon,
  DocumentTextIcon,
  CubeIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  PlusIcon,
  MinusIcon,
  PlayIcon,
  XMarkIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  FunnelIcon,
  LightBulbIcon,
  LinkIcon,
  CircleStackIcon,
  ExclamationTriangleIcon,
  CommandLineIcon,
  ShareIcon,
  ClipboardDocumentIcon,
  ArrowTopRightOnSquareIcon,
  EyeIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';
import { PageSkeleton } from './ui/LoadingSkeleton';
import FileViewer from './graph/FileViewer';
import { useToast } from './ui/Toast';

// =============================================================================
// Design System Constants
// =============================================================================

const NODE_TYPES = {
  file: {
    color: '#3B82F6', // aura blue
    darkColor: '#60A5FA',
    icon: DocumentTextIcon,
    label: 'File',
  },
  class: {
    color: '#7C9A3E', // olive
    darkColor: '#9FB87A',
    icon: CubeIcon,
    label: 'Class',
  },
  function: {
    color: '#6B7280', // gray
    darkColor: '#9CA3AF',
    icon: CommandLineIcon,
    label: 'Function',
  },
  dependency: {
    color: '#F59E0B', // warning amber
    darkColor: '#FBBF24',
    icon: LinkIcon,
    label: 'Dependency',
  },
  vulnerability: {
    color: '#DC2626', // critical red
    darkColor: '#F87171',
    icon: ExclamationTriangleIcon,
    label: 'Vulnerability',
  },
};

const EDGE_TYPES = {
  imports: { color: '#3B82F6', label: 'Imports' },
  extends: { color: '#7C9A3E', label: 'Extends' },
  implements: { color: '#8B5CF6', label: 'Implements' },
  calls: { color: '#6B7280', label: 'Calls' },
  depends: { color: '#F59E0B', label: 'Depends On' },
  affects: { color: '#DC2626', label: 'Affects' },
};

// =============================================================================
// Mock Data - Graph Nodes and Edges
// =============================================================================

const MOCK_NODES = [
  // Files
  {
    id: 'file-1',
    type: 'file',
    label: 'UserController.java',
    path: 'src/controllers/UserController.java',
    lines: 245,
    summary: 'REST API controller handling user CRUD operations and profile management endpoints.',
    impact_summary: 'Entry point for all user-related API calls. Affects authentication flow.',
  },
  {
    id: 'file-2',
    type: 'file',
    label: 'AuthService.py',
    path: 'src/services/auth_service.py',
    lines: 189,
    summary: 'Core authentication service implementing OAuth2 and session management.',
    impact_summary: 'Central auth dependency. 8 services rely on this for access control.',
  },
  {
    id: 'file-3',
    type: 'file',
    label: 'DatabaseConnector.java',
    path: 'src/db/DatabaseConnector.java',
    lines: 312,
    summary: 'Database connection pool manager with query execution and transaction support.',
    impact_summary: 'Critical data layer. All database operations flow through this connector.',
  },
  {
    id: 'file-4',
    type: 'file',
    label: 'JWTValidator.py',
    path: 'src/auth/jwt_validator.py',
    lines: 156,
    summary: 'JWT token validation with signature verification and expiration checking.',
    impact_summary: 'Security-critical component used by all authenticated endpoints.',
  },
  // Classes
  {
    id: 'class-1',
    type: 'class',
    label: 'UserController',
    methods: 12,
    attributes: 5,
    summary: 'Handles user authentication, profile updates, and account management endpoints.',
    impact_summary: 'Central controller affecting 8 downstream services and auth flow.',
  },
  {
    id: 'class-2',
    type: 'class',
    label: 'AuthService',
    methods: 8,
    attributes: 3,
    summary: 'Manages user sessions, token generation, and credential validation.',
    impact_summary: 'Core security service. Changes here affect entire authentication system.',
  },
  {
    id: 'class-3',
    type: 'class',
    label: 'DatabaseConnector',
    methods: 15,
    attributes: 7,
    summary: 'Provides pooled database connections and executes parameterized queries.',
    impact_summary: 'Data access layer used by all repository classes.',
  },
  {
    id: 'class-4',
    type: 'class',
    label: 'JWTValidator',
    methods: 6,
    attributes: 2,
    summary: 'Validates JWT tokens, checks claims, and verifies cryptographic signatures.',
    impact_summary: 'API security gateway. All protected endpoints depend on this.',
  },
  // Functions
  {
    id: 'func-1',
    type: 'function',
    label: 'getUserById()',
    complexity: 5,
    calls: 23,
    summary: 'Retrieves user record from database by unique identifier with caching.',
    impact_summary: 'Called by profile, admin, and reporting modules.',
  },
  {
    id: 'func-2',
    type: 'function',
    label: 'validateToken()',
    complexity: 8,
    calls: 45,
    summary: 'Validates JWT signature, expiration, and required claims for authentication.',
    impact_summary: 'Security-critical. Called on every authenticated API request.',
  },
  {
    id: 'func-3',
    type: 'function',
    label: 'executeQuery()',
    complexity: 12,
    calls: 67,
    summary: 'Executes parameterized SQL queries with connection pooling and retry logic.',
    impact_summary: 'Core database function. All data operations depend on this.',
  },
  {
    id: 'func-4',
    type: 'function',
    label: 'hashPassword()',
    complexity: 3,
    calls: 12,
    summary: 'Hashes passwords using Argon2id with configurable memory and iteration params.',
    impact_summary: 'Used during registration and password reset flows.',
  },
  // Dependencies
  {
    id: 'dep-1',
    type: 'dependency',
    label: 'spring-boot-2.7.0',
    version: '2.7.0',
    risk: 'low',
    summary: 'Application framework providing dependency injection and web server.',
    impact_summary: 'Core framework. Upgrading affects entire application structure.',
    docs_url: 'https://spring.io/projects/spring-boot',
  },
  {
    id: 'dep-2',
    type: 'dependency',
    label: 'log4j-2.17.0',
    version: '2.17.0',
    risk: 'medium',
    summary: 'Logging framework for application diagnostics and audit trails.',
    impact_summary: 'Used across all modules for logging. Patched for CVE-2021-44228.',
    docs_url: 'https://logging.apache.org/log4j/2.x/',
  },
  {
    id: 'dep-3',
    type: 'dependency',
    label: 'jwt-library-1.4.0',
    version: '1.4.0',
    risk: 'high',
    summary: 'JWT signing and verification library with RS256/HS256 support.',
    impact_summary: 'Security dependency. Vulnerability here exposes all auth endpoints.',
    // No docs_url - tests fallback state
  },
  // Vulnerabilities
  {
    id: 'vuln-1',
    type: 'vulnerability',
    label: 'CVE-2024-1234',
    severity: 'critical',
    cwe: 'CWE-89',
    summary: 'SQL injection vulnerability in query parameter handling allows DB access.',
    impact_summary: 'Affects getUserById() and executeQuery(). Immediate patch required.',
    docs_url: 'https://nvd.nist.gov/vuln/detail/CVE-2024-1234',
  },
  {
    id: 'vuln-2',
    type: 'vulnerability',
    label: 'CVE-2024-5678',
    severity: 'high',
    cwe: 'CWE-79',
    summary: 'Cross-site scripting in user profile display allows script injection.',
    impact_summary: 'Affects UserController rendering. User input not properly escaped.',
    docs_url: 'https://nvd.nist.gov/vuln/detail/CVE-2024-5678',
  },
];

const MOCK_EDGES = [
  // File -> Class relationships
  { source: 'file-1', target: 'class-1', type: 'imports' },
  { source: 'file-2', target: 'class-2', type: 'imports' },
  { source: 'file-3', target: 'class-3', type: 'imports' },
  { source: 'file-4', target: 'class-4', type: 'imports' },
  // Class -> Function relationships
  { source: 'class-1', target: 'func-1', type: 'calls' },
  { source: 'class-2', target: 'func-2', type: 'calls' },
  { source: 'class-3', target: 'func-3', type: 'calls' },
  { source: 'class-2', target: 'func-4', type: 'calls' },
  // Class dependencies
  { source: 'class-1', target: 'class-3', type: 'depends' },
  { source: 'class-2', target: 'class-4', type: 'depends' },
  { source: 'class-1', target: 'class-2', type: 'depends' },
  // Dependency relationships
  { source: 'file-1', target: 'dep-1', type: 'depends' },
  { source: 'file-3', target: 'dep-2', type: 'depends' },
  { source: 'file-4', target: 'dep-3', type: 'depends' },
  // Vulnerability relationships
  { source: 'vuln-1', target: 'func-1', type: 'affects' },
  { source: 'vuln-1', target: 'func-3', type: 'affects' },
  { source: 'vuln-2', target: 'class-1', type: 'affects' },
];

const _MOCK_QUERY_HISTORY = [
  { id: 1, query: 'Find all SQL injection vulnerabilities', timestamp: '2024-12-08T10:30:00Z', results: 3 },
  { id: 2, query: 'Show classes affected by CVE-2024-1234', timestamp: '2024-12-08T10:15:00Z', results: 2 },
  { id: 3, query: 'List all external dependencies with high risk', timestamp: '2024-12-08T09:45:00Z', results: 1 },
  { id: 4, query: 'Find functions with complexity > 10', timestamp: '2024-12-08T09:30:00Z', results: 4 },
];

// =============================================================================
// Helper Functions
// =============================================================================

// Calculate optimal label position based on neighboring nodes
const calculateLabelPosition = (nodeId, nodePositions, edges) => {
  const node = nodePositions[nodeId];
  if (!node) return { offsetX: 0, offsetY: 35, anchor: 'middle' };

  const connectedNodes = edges
    .filter(e => e.source === nodeId || e.target === nodeId)
    .map(e => e.source === nodeId ? e.target : e.source);

  if (connectedNodes.length === 0) {
    return { offsetX: 0, offsetY: 35, anchor: 'middle' };
  }

  // Calculate centroid of connected nodes
  let totalX = 0, totalY = 0, count = 0;
  connectedNodes.forEach(id => {
    const pos = nodePositions[id];
    if (pos) {
      totalX += pos.x;
      totalY += pos.y;
      count++;
    }
  });

  if (count === 0) return { offsetX: 0, offsetY: 35, anchor: 'middle' };

  const avgX = totalX / count;
  const avgY = totalY / count;

  // Position label opposite to neighbor centroid
  const angle = Math.atan2(avgY - node.y, avgX - node.x);
  const labelAngle = angle + Math.PI;

  // Determine best anchor position
  const offsetX = Math.cos(labelAngle) * 35;
  const offsetY = Math.sin(labelAngle) * 35 + 10;

  let anchor = 'middle';
  if (offsetX > 15) anchor = 'start';
  else if (offsetX < -15) anchor = 'end';

  return { offsetX, offsetY, anchor };
};

// Get label opacity based on zoom level
const getLabelOpacity = (zoom, isHovered, isSelected) => {
  if (isSelected || isHovered) return 1;
  if (zoom < 0.5) return 0;
  if (zoom < 0.7) return 0.4;
  return 1;
};

// Truncate label text
const truncateLabel = (label, maxLength = 18) => {
  return label.length > maxLength ? label.substring(0, maxLength) + '...' : label;
};

// Calculate curved edge path using quadratic bezier
const getEdgePath = (sourcePos, targetPos, edgeIndex = 0) => {
  const midX = (sourcePos.x + targetPos.x) / 2;
  const midY = (sourcePos.y + targetPos.y) / 2;

  const dx = targetPos.x - sourcePos.x;
  const dy = targetPos.y - sourcePos.y;
  const length = Math.sqrt(dx * dx + dy * dy) || 1;

  // Perpendicular unit vector
  const perpX = -dy / length;
  const perpY = dx / length;

  // Offset amount (alternate direction for multiple edges between same nodes)
  const offset = 20 * (edgeIndex % 2 === 0 ? 1 : -1) * Math.ceil((edgeIndex + 1) / 2);

  const controlX = midX + perpX * offset;
  const controlY = midY + perpY * offset;

  return `M ${sourcePos.x} ${sourcePos.y} Q ${controlX} ${controlY} ${targetPos.x} ${targetPos.y}`;
};

// =============================================================================
// Graph Visualization Component (Canvas-based)
// =============================================================================

function GraphCanvas({ nodes, edges, selectedNode, onNodeSelect, onNodeDoubleClick, onContextMenu, zoom, pan, onPanChange, onZoomChange }) {
  const canvasRef = useRef(null);
  const [nodePositions, setNodePositions] = useState({});
  const [hoveredNode, setHoveredNode] = useState(null);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const animationRef = useRef(null);

  // Initialize node positions using force-directed layout simulation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;
    const centerX = width / 2;
    const centerY = height / 2;

    // Simple force-directed layout initialization
    const positions = {};
    const nodesByType = {};

    // Group nodes by type for clustering
    nodes.forEach((node) => {
      if (!nodesByType[node.type]) nodesByType[node.type] = [];
      nodesByType[node.type].push(node);
    });

    // Position nodes in clusters by type
    const typeAngles = {
      file: 0,
      class: Math.PI / 2,
      function: Math.PI,
      dependency: (3 * Math.PI) / 2,
      vulnerability: Math.PI / 4,
    };

    Object.entries(nodesByType).forEach(([type, typeNodes]) => {
      const baseAngle = typeAngles[type] || 0;
      const radius = 150 + Math.random() * 50;

      typeNodes.forEach((node, index) => {
        const angle = baseAngle + (index * 0.3) - (typeNodes.length * 0.15);
        const r = radius + index * 30;
        positions[node.id] = {
          x: centerX + Math.cos(angle) * r,
          y: centerY + Math.sin(angle) * r,
          vx: 0,
          vy: 0,
        };
      });
    });

    setNodePositions(positions);

    // Force simulation constants
    const MIN_NODE_DISTANCE = 80;
    const REPULSION_FORCE = 4000;

    // Simple force simulation
    let iteration = 0;
    const maxIterations = 100;

    const simulate = () => {
      if (iteration >= maxIterations) return;

      const newPositions = { ...positions };

      // Apply forces
      nodes.forEach((node) => {
        if (!newPositions[node.id]) return;

        let fx = 0, fy = 0;

        // Repulsion from other nodes with minimum distance enforcement
        nodes.forEach((other) => {
          if (node.id === other.id || !newPositions[other.id]) return;

          const dx = newPositions[node.id].x - newPositions[other.id].x;
          const dy = newPositions[node.id].y - newPositions[other.id].y;
          let dist = Math.sqrt(dx * dx + dy * dy) || 1;

          // Hard minimum distance enforcement
          if (dist < MIN_NODE_DISTANCE) {
            const overlap = MIN_NODE_DISTANCE - dist;
            const pushX = (dx / dist) * overlap * 0.5;
            const pushY = (dy / dist) * overlap * 0.5;
            newPositions[node.id].x += pushX;
            newPositions[node.id].y += pushY;
            newPositions[other.id].x -= pushX;
            newPositions[other.id].y -= pushY;
            dist = MIN_NODE_DISTANCE;
          }

          const force = REPULSION_FORCE / (dist * dist);
          fx += (dx / dist) * force;
          fy += (dy / dist) * force;
        });

        // Attraction along edges
        edges.forEach((edge) => {
          let otherId = null;
          if (edge.source === node.id) otherId = edge.target;
          else if (edge.target === node.id) otherId = edge.source;

          if (otherId && newPositions[otherId]) {
            const dx = newPositions[otherId].x - newPositions[node.id].x;
            const dy = newPositions[otherId].y - newPositions[node.id].y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = dist * 0.01;

            fx += (dx / dist) * force;
            fy += (dy / dist) * force;
          }
        });

        // Center gravity
        fx += (centerX - newPositions[node.id].x) * 0.001;
        fy += (centerY - newPositions[node.id].y) * 0.001;

        // Apply velocity with damping
        newPositions[node.id].vx = (newPositions[node.id].vx + fx) * 0.9;
        newPositions[node.id].vy = (newPositions[node.id].vy + fy) * 0.9;
        newPositions[node.id].x += newPositions[node.id].vx;
        newPositions[node.id].y += newPositions[node.id].vy;

        // Keep within bounds
        newPositions[node.id].x = Math.max(50, Math.min(width - 50, newPositions[node.id].x));
        newPositions[node.id].y = Math.max(50, Math.min(height - 50, newPositions[node.id].y));
      });

      Object.assign(positions, newPositions);
      setNodePositions({ ...positions });

      iteration++;
      animationRef.current = requestAnimationFrame(simulate);
    };

    simulate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [nodes, edges]);

  // Handle mouse events for panning
  const handleMouseDown = useCallback((e) => {
    // Only pan if not clicking on a node
    if (!hoveredNode) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  }, [hoveredNode, pan]);

  const handleMouseMove = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Handle panning
    if (isPanning && onPanChange) {
      const newPan = {
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      };
      onPanChange(newPan);
      return;
    }

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - pan.x) / zoom;
    const y = (e.clientY - rect.top - pan.y) / zoom;

    // Check if hovering over a node
    let found = null;
    nodes.forEach((node) => {
      const pos = nodePositions[node.id];
      if (!pos) return;

      const dx = x - pos.x;
      const dy = y - pos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < 25) {
        found = node;
      }
    });

    setHoveredNode(found);
  }, [nodes, nodePositions, zoom, pan, isPanning, panStart, onPanChange]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsPanning(false);
    setHoveredNode(null);
  }, []);

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    if (!onZoomChange) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Zoom factor (scroll up = zoom in, scroll down = zoom out)
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    const newZoom = Math.min(Math.max(zoom * zoomFactor, 0.3), 3);

    // Adjust pan to zoom toward mouse position
    if (onPanChange) {
      const scaleDiff = newZoom - zoom;
      const newPan = {
        x: pan.x - (mouseX - pan.x) * (scaleDiff / zoom),
        y: pan.y - (mouseY - pan.y) * (scaleDiff / zoom),
      };
      onPanChange(newPan);
    }

    onZoomChange(newZoom);
  }, [zoom, pan, onZoomChange, onPanChange]);

  const handleClick = useCallback((_e) => {
    if (hoveredNode && !isPanning) {
      onNodeSelect(hoveredNode);
    }
  }, [hoveredNode, isPanning, onNodeSelect]);

  const handleDoubleClick = useCallback((_e) => {
    if (hoveredNode && onNodeDoubleClick) {
      onNodeDoubleClick(hoveredNode);
    }
  }, [hoveredNode, onNodeDoubleClick]);

  const handleContextMenuEvent = useCallback((e) => {
    if (hoveredNode && onContextMenu) {
      e.preventDefault();
      onContextMenu(e, hoveredNode);
    }
  }, [hoveredNode, onContextMenu]);

  // Render graph
  const isDarkMode = document.documentElement.classList.contains('dark');

  return (
    <div
      ref={canvasRef}
      className="w-full h-full bg-surface-50 dark:bg-surface-900 rounded-lg relative overflow-hidden select-none"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
      onWheel={handleWheel}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onContextMenu={handleContextMenuEvent}
      style={{ cursor: isPanning ? 'grabbing' : hoveredNode ? 'pointer' : 'grab' }}
    >
      <svg
        className="w-full h-full"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: '0 0',
        }}
      >
        {/* Edges (curved bezier paths) */}
        {edges.map((edge, index) => {
          const sourcePos = nodePositions[edge.source];
          const targetPos = nodePositions[edge.target];
          if (!sourcePos || !targetPos) return null;

          const edgeType = EDGE_TYPES[edge.type] || EDGE_TYPES.calls;
          const isHighlighted = selectedNode && (edge.source === selectedNode.id || edge.target === selectedNode.id);

          return (
            <path
              key={index}
              d={getEdgePath(sourcePos, targetPos, index)}
              stroke={edgeType.color}
              strokeWidth={isHighlighted ? 2.5 : 1.5}
              strokeOpacity={isHighlighted ? 1 : 0.5}
              strokeDasharray={edge.type === 'affects' ? '5,5' : 'none'}
              fill="none"
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const pos = nodePositions[node.id];
          if (!pos) return null;

          const nodeType = NODE_TYPES[node.type] || NODE_TYPES.file;
          const isSelected = selectedNode?.id === node.id;
          const isHovered = hoveredNode?.id === node.id;
          const color = isDarkMode ? nodeType.darkColor : nodeType.color;

          return (
            <g key={node.id} className="transition-transform duration-150">
              {/* Node glow for selected/hovered */}
              {(isSelected || isHovered) && (
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={30}
                  fill={color}
                  opacity={0.2}
                  className="animate-pulse"
                />
              )}

              {/* Node circle */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={isSelected ? 24 : isHovered ? 22 : 20}
                fill={isDarkMode ? '#1F2937' : '#FFFFFF'}
                stroke={color}
                strokeWidth={isSelected ? 4 : isHovered ? 3 : 2}
                className="transition-all duration-150"
              />

              {/* Node icon placeholder */}
              <text
                x={pos.x}
                y={pos.y}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize="12"
                fontWeight="bold"
                fill={color}
              >
                {node.type.charAt(0).toUpperCase()}
              </text>

              {/* Node label with smart positioning and background halo */}
              {(() => {
                const labelPos = calculateLabelPosition(node.id, nodePositions, edges);
                const labelOpacity = getLabelOpacity(zoom, isHovered, isSelected);
                const labelText = truncateLabel(node.label, 18);
                const labelX = pos.x + labelPos.offsetX;
                const labelY = pos.y + labelPos.offsetY;

                // Estimate text width (approximate)
                const textWidth = labelText.length * 6;
                let rectX = labelX - textWidth / 2 - 4;
                if (labelPos.anchor === 'start') rectX = labelX - 4;
                else if (labelPos.anchor === 'end') rectX = labelX - textWidth - 4;

                return labelOpacity > 0 ? (
                  <g
                    className="pointer-events-none"
                    style={{
                      opacity: labelOpacity,
                      transition: 'opacity 200ms ease-out'
                    }}
                  >
                    {/* Label background halo */}
                    <rect
                      x={rectX}
                      y={labelY - 9}
                      width={textWidth + 8}
                      height={14}
                      rx={3}
                      fill={isDarkMode ? 'rgba(17,24,39,0.85)' : 'rgba(255,255,255,0.9)'}
                    />
                    {/* Label text */}
                    <text
                      x={labelX}
                      y={labelY}
                      textAnchor={labelPos.anchor}
                      fontSize="11"
                      fontWeight="500"
                      fill={isDarkMode ? '#D1D5DB' : '#374151'}
                    >
                      {labelText}
                    </text>
                  </g>
                ) : null;
              })()}
            </g>
          );
        })}
      </svg>

      {/* Hovered node tooltip */}
      {hoveredNode && nodePositions[hoveredNode.id] && (
        <div
          className="absolute bg-surface-900 dark:bg-white text-white dark:text-surface-900 px-3 py-2 rounded-lg text-xs shadow-lg pointer-events-none z-10"
          style={{
            left: nodePositions[hoveredNode.id].x * zoom + pan.x + 30,
            top: nodePositions[hoveredNode.id].y * zoom + pan.y - 20,
          }}
        >
          <p className="font-semibold">{hoveredNode.label}</p>
          <p className="opacity-75">{NODE_TYPES[hoveredNode.type]?.label || hoveredNode.type}</p>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Query Builder Component
// =============================================================================

function QueryBuilder({ onExecute, isLoading }) {
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);

  const suggestions = [
    'Find all SQL injection vulnerabilities',
    'Show classes with high cyclomatic complexity',
    'List functions that access sensitive data',
    'Find unused dependencies',
    'Show all CVEs affecting authentication',
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onExecute(query.trim());
    }
  };

  return (
    <div className="p-4 border-b border-surface-200 dark:border-surface-700">
      <form onSubmit={handleSubmit} className="relative">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              placeholder="Ask a question..."
              className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="flex items-center gap-2 px-4 py-2.5 bg-olive-500 hover:bg-olive-600 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <ArrowPathIcon className="w-5 h-5 animate-spin" />
            ) : (
              <PlayIcon className="w-5 h-5" />
            )}
            Execute
          </button>
        </div>

        {/* Suggestions dropdown */}
        {showSuggestions && (
          <div className="absolute z-20 left-0 right-0 mt-1 bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg shadow-lg overflow-hidden">
            <div className="p-2 border-b border-surface-200 dark:border-surface-700">
              <p className="text-xs text-surface-500 dark:text-surface-400 font-medium flex items-center gap-1">
                <LightBulbIcon className="w-4 h-4" />
                Suggested Queries
              </p>
            </div>
            {suggestions.map((suggestion, index) => (
              <button
                key={index}
                type="button"
                onClick={() => {
                  setQuery(suggestion);
                  setShowSuggestions(false);
                }}
                className="w-full text-left px-4 py-2 text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </form>
    </div>
  );
}

// =============================================================================
// Helper: Get relationships for a node from edges
// =============================================================================

const getNodeRelationships = (nodeId, edges, nodes) => {
  const incoming = [];
  const outgoing = [];
  const affectedBy = [];

  edges.forEach(edge => {
    if (edge.target === nodeId) {
      const sourceNode = nodes.find(n => n.id === edge.source);
      if (sourceNode) {
        if (edge.type === 'affects') {
          affectedBy.push({ type: edge.type, node: sourceNode });
        } else {
          incoming.push({ type: edge.type, node: sourceNode });
        }
      }
    }
    if (edge.source === nodeId) {
      const targetNode = nodes.find(n => n.id === edge.target);
      if (targetNode) {
        if (edge.type === 'affects') {
          affectedBy.push({ type: edge.type, node: targetNode });
        } else {
          outgoing.push({ type: edge.type, node: targetNode });
        }
      }
    }
  });

  return { incoming, outgoing, affectedBy };
};

// =============================================================================
// Documentation Link Component
// =============================================================================

function DocumentationLink({ node }) {
  // Only show for dependency and vulnerability nodes
  if (!['dependency', 'vulnerability'].includes(node?.type)) {
    return null;
  }

  const getSearchUrl = (name) => {
    const encodedName = encodeURIComponent(name);
    return `https://duckduckgo.com/?q=${encodedName}+documentation`;
  };

  const getDisplayUrl = (url) => {
    try {
      const parsed = new URL(url);
      const path = parsed.pathname.length > 25
        ? parsed.pathname.slice(0, 25) + '...'
        : parsed.pathname;
      return parsed.hostname + path;
    } catch {
      return url;
    }
  };

  // Documentation available
  if (node.docs_url) {
    return (
      <div className="border-t border-surface-100 dark:border-surface-700 pt-3 mt-3">
        <a
          href={node.docs_url}
          target="_blank"
          rel="noopener noreferrer"
          className="group flex items-start gap-3 p-2 -mx-2 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors duration-200"
        >
          <DocumentTextIcon className="w-5 h-5 text-surface-400 mt-0.5 group-hover:text-aura-500 transition-colors duration-200" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-medium text-surface-700 dark:text-surface-300 group-hover:text-aura-600 dark:group-hover:text-aura-400 transition-colors duration-200">
                Official Documentation
              </span>
              <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5 text-surface-400 group-hover:text-aura-500 transition-colors duration-200" />
            </div>
            <span className="text-xs text-surface-500 truncate block mt-0.5">
              {getDisplayUrl(node.docs_url)}
            </span>
          </div>
        </a>
      </div>
    );
  }

  // No documentation available - show fallback
  return (
    <div className="border-t border-surface-100 dark:border-surface-700 pt-3 mt-3">
      <div className="flex items-start gap-3 p-2 -mx-2">
        <div className="w-5 h-5 rounded-full border-2 border-dashed border-surface-300 dark:border-surface-600 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm text-surface-500 dark:text-surface-400">
            No official documentation available
          </p>
          <div className="flex items-center gap-1.5 mt-1.5">
            <span className="text-xs text-surface-400">Search on:</span>
            <a
              href={getSearchUrl(node.label)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-aura-500 hover:text-aura-600 dark:text-aura-400 dark:hover:text-aura-300 hover:underline inline-flex items-center gap-1"
            >
              Internet
              <ArrowTopRightOnSquareIcon className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Relationship Section Component
// =============================================================================

function RelationshipSection({ title, relationships, isExpanded, onToggle, onNodeClick, maxVisible = 5 }) {
  const [showAll, setShowAll] = useState(false);
  const count = relationships.length;
  const displayedRelationships = showAll ? relationships : relationships.slice(0, maxVisible);
  const hasMore = count > maxVisible;

  if (count === 0) {
    return null;
  }

  return (
    <div className="border-b border-surface-100 dark:border-surface-700 last:border-b-0">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-2 hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors"
      >
        <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
          {title} ({count})
        </span>
        {isExpanded ? (
          <ChevronUpIcon className="w-4 h-4 text-surface-400" />
        ) : (
          <ChevronDownIcon className="w-4 h-4 text-surface-400" />
        )}
      </button>

      {isExpanded && (
        <div className="pb-2 px-2 space-y-1">
          {displayedRelationships.map((rel, index) => {
            const _nodeType = NODE_TYPES[rel.node.type] || NODE_TYPES.file;
            const edgeType = EDGE_TYPES[rel.type] || { label: rel.type };

            return (
              <button
                key={index}
                onClick={() => onNodeClick(rel.node)}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-100 dark:hover:bg-surface-600 transition-colors text-left group"
              >
                <span
                  className="text-xs px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-600 text-surface-500 dark:text-surface-400"
                >
                  {edgeType.label}
                </span>
                <span className="flex-1 text-sm text-surface-700 dark:text-surface-300 truncate">
                  {rel.node.label}
                </span>
                <ChevronRightIcon className="w-3 h-3 text-surface-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              </button>
            );
          })}

          {hasMore && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="w-full text-center py-1 text-xs text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
            >
              {showAll ? 'Show less' : `+ Show ${count - maxVisible} more`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Node Detail Panel
// =============================================================================

function NodeDetailPanel({ node, edges, nodes, onClose, onNodeClick, onCenterNode, onFilterConnected, onOpenFile }) {
  const [expandedSections, setExpandedSections] = useState({
    incoming: true,
    outgoing: false,
    affectedBy: false,
  });
  const [copiedId, setCopiedId] = useState(false);

  if (!node) {
    return (
      <div className="p-6 text-center text-surface-400 dark:text-surface-500">
        <CircleStackIcon className="w-12 h-12 mx-auto mb-3" />
        <p className="font-medium">Select a node</p>
        <p className="text-sm">Click on a node in the graph to view details</p>
      </div>
    );
  }

  const nodeType = NODE_TYPES[node.type] || NODE_TYPES.file;
  const NodeIcon = nodeType.icon;
  const relationships = getNodeRelationships(node.id, edges || [], nodes || []);

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const handleCopyId = async () => {
    try {
      await navigator.clipboard.writeText(node.id);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleOpenCode = () => {
    if (node.path && onOpenFile) {
      onOpenFile(node);
    }
  };

  const renderNodeDetails = () => {
    switch (node.type) {
      case 'file':
        return (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">Path</span>
              <span className="font-mono text-xs text-surface-900 dark:text-surface-100 truncate max-w-[180px]">{node.path}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">Lines</span>
              <span className="text-surface-900 dark:text-surface-100">{node.lines}</span>
            </div>
          </div>
        );
      case 'class':
        return (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">Methods</span>
              <span className="text-surface-900 dark:text-surface-100">{node.methods}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">Attributes</span>
              <span className="text-surface-900 dark:text-surface-100">{node.attributes}</span>
            </div>
          </div>
        );
      case 'function':
        return (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">Complexity</span>
              <span className={`text-sm font-medium ${node.complexity > 10 ? 'text-critical-600' : node.complexity > 5 ? 'text-warning-600' : 'text-olive-600'}`}>
                {node.complexity}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">Call Count</span>
              <span className="text-surface-900 dark:text-surface-100">{node.calls}</span>
            </div>
          </div>
        );
      case 'dependency':
        return (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">Version</span>
              <span className="text-surface-900 dark:text-surface-100">{node.version}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">Risk</span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                node.risk === 'high' ? 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400' :
                node.risk === 'medium' ? 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400' :
                'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400'
              }`}>
                {node.risk}
              </span>
            </div>
          </div>
        );
      case 'vulnerability':
        return (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">Severity</span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium uppercase ${
                node.severity === 'critical' ? 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400' :
                node.severity === 'high' ? 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400' :
                'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400'
              }`}>
                {node.severity}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-surface-500 dark:text-surface-400">CWE</span>
              <span className="font-mono text-surface-900 dark:text-surface-100">{node.cwe}</span>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  const totalRelationships = relationships.incoming.length + relationships.outgoing.length + relationships.affectedBy.length;

  return (
    <div className="border-b border-surface-200 dark:border-surface-700 flex flex-col">
      {/* Header */}
      <div className="p-4 pb-3">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div
              className="p-2 rounded-lg"
              style={{ backgroundColor: `${nodeType.color}20` }}
            >
              <NodeIcon className="w-5 h-5" style={{ color: nodeType.color }} />
            </div>
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">
                {node.label}
              </h3>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                {nodeType.label}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-surface-100 dark:hover:bg-surface-700 rounded transition-colors"
          >
            <XMarkIcon className="w-4 h-4 text-surface-400" />
          </button>
        </div>

        {/* Description */}
        {node.summary && (
          <div className="mb-3 space-y-2">
            <div>
              <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">Summary</span>
              <p className="text-sm text-surface-700 dark:text-surface-300 leading-relaxed mt-0.5">
                {node.summary}
              </p>
            </div>
            {node.impact_summary && (
              <div>
                <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">Impact</span>
                <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed mt-0.5">
                  {node.impact_summary}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Properties */}
        <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-3">
          {renderNodeDetails()}
        </div>

        {/* Documentation Link (dependencies and vulnerabilities only) */}
        <DocumentationLink node={node} />

        {/* Action Bar */}
        <div className="flex items-center gap-1 mt-3">
          {onCenterNode && (
            <button
              onClick={() => onCenterNode(node)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              title="Center in view (C)"
            >
              <ArrowsPointingOutIcon className="w-3.5 h-3.5" />
              Center
            </button>
          )}
          <button
            onClick={handleCopyId}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            title="Copy node ID"
          >
            <ClipboardDocumentIcon className="w-3.5 h-3.5" />
            {copiedId ? 'Copied!' : 'Copy ID'}
          </button>
          {onFilterConnected && totalRelationships > 0 && (
            <button
              onClick={() => onFilterConnected(node)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              title="Filter to connected nodes (F)"
            >
              <FunnelIcon className="w-3.5 h-3.5" />
              Filter
            </button>
          )}
          {node.path && (
            <button
              onClick={handleOpenCode}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              title="Open source file (O)"
            >
              <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
              Open
            </button>
          )}
        </div>
      </div>

      {/* Relationships */}
      {totalRelationships > 0 && (
        <div className="border-t border-surface-100 dark:border-surface-700">
          <RelationshipSection
            title="Incoming"
            relationships={relationships.incoming}
            isExpanded={expandedSections.incoming}
            onToggle={() => toggleSection('incoming')}
            onNodeClick={onNodeClick || (() => {})}
          />
          <RelationshipSection
            title="Outgoing"
            relationships={relationships.outgoing}
            isExpanded={expandedSections.outgoing}
            onToggle={() => toggleSection('outgoing')}
            onNodeClick={onNodeClick || (() => {})}
          />
          {relationships.affectedBy.length > 0 && (
            <RelationshipSection
              title="Affected by"
              relationships={relationships.affectedBy}
              isExpanded={expandedSections.affectedBy}
              onToggle={() => toggleSection('affectedBy')}
              onNodeClick={onNodeClick || (() => {})}
            />
          )}
        </div>
      )}

      {totalRelationships === 0 && (
        <div className="px-4 pb-3">
          <p className="text-xs text-surface-400 dark:text-surface-500 text-center py-2">
            No connections
          </p>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Query Results Component
// =============================================================================

function QueryResults({ results, onNodeClick }) {
  if (!results || results.length === 0) {
    return (
      <div className="p-6 text-center text-surface-400 dark:text-surface-500">
        <FunnelIcon className="w-12 h-12 mx-auto mb-3" />
        <p className="font-medium">No results</p>
        <p className="text-sm">Execute a query to see results</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-surface-900 dark:text-surface-100">Results</h3>
        <span className="text-xs text-surface-500 dark:text-surface-400">
          {results.length} nodes found
        </span>
      </div>
      <div className="space-y-2 max-h-[300px] overflow-y-auto">
        {results.map((node) => {
          const nodeType = NODE_TYPES[node.type] || NODE_TYPES.file;
          const NodeIcon = nodeType.icon;

          return (
            <button
              key={node.id}
              onClick={() => onNodeClick(node)}
              className="w-full flex items-center gap-3 p-2 bg-surface-50 dark:bg-surface-700/50 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors text-left"
            >
              <NodeIcon className="w-4 h-4" style={{ color: nodeType.color }} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                  {node.label}
                </p>
                <p className="text-xs text-surface-500 dark:text-surface-400">
                  {nodeType.label}
                </p>
              </div>
              <ChevronRightIcon className="w-4 h-4 text-surface-400" />
            </button>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// Graph Metrics Component
// =============================================================================

function GraphMetrics({ nodes, edges }) {
  const metrics = {
    totalNodes: nodes.length,
    totalEdges: edges.length,
    files: nodes.filter(n => n.type === 'file').length,
    classes: nodes.filter(n => n.type === 'class').length,
    functions: nodes.filter(n => n.type === 'function').length,
    vulnerabilities: nodes.filter(n => n.type === 'vulnerability').length,
  };

  return (
    <div className="p-4 border-t border-surface-200 dark:border-surface-700">
      <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Graph Metrics</h3>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-2 text-center">
          <p className="text-lg font-bold text-aura-600 dark:text-aura-400">{metrics.totalNodes}</p>
          <p className="text-xs text-surface-500 dark:text-surface-400">Nodes</p>
        </div>
        <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-2 text-center">
          <p className="text-lg font-bold text-olive-600 dark:text-olive-400">{metrics.totalEdges}</p>
          <p className="text-xs text-surface-500 dark:text-surface-400">Edges</p>
        </div>
        <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-2 text-center">
          <p className="text-lg font-bold text-surface-600 dark:text-surface-400">{metrics.classes}</p>
          <p className="text-xs text-surface-500 dark:text-surface-400">Classes</p>
        </div>
        <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-2 text-center">
          <p className="text-lg font-bold text-critical-600 dark:text-critical-400">{metrics.vulnerabilities}</p>
          <p className="text-xs text-surface-500 dark:text-surface-400">CVEs</p>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Context Menu Component
// =============================================================================

function NodeContextMenu({ position, node, onAction, onClose }) {
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose();
      }
    };

    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose();
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  if (!position || !node) return null;

  const nodeType = NODE_TYPES[node.type] || NODE_TYPES.file;
  const NodeIcon = nodeType.icon;

  const menuItems = [
    { id: 'viewFile', icon: EyeIcon, label: 'View File', enabled: !!node.path },
    { id: 'viewReferences', icon: LinkIcon, label: 'View References', enabled: true },
    { id: 'copyPath', icon: DocumentDuplicateIcon, label: 'Copy Path', enabled: !!node.path },
    { id: 'openInIDE', icon: ArrowTopRightOnSquareIcon, label: 'Open in IDE', enabled: !!node.path },
  ];

  // Adjust position to stay within viewport
  const adjustedX = Math.min(position.x, window.innerWidth - 200);
  const adjustedY = Math.min(position.y, window.innerHeight - 220);

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-white dark:bg-surface-800 rounded-xl shadow-xl border border-surface-200 dark:border-surface-700 py-2 min-w-[180px] animate-in fade-in zoom-in-95 duration-150"
      style={{ left: adjustedX, top: adjustedY }}
    >
      {/* Header */}
      <div className="px-3 py-2 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-2">
          <NodeIcon className="w-4 h-4" style={{ color: nodeType.color }} />
          <div>
            <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate max-w-[140px]">
              {node.label}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              {nodeType.label}
            </p>
          </div>
        </div>
      </div>

      {/* Menu Items */}
      <div className="py-1">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => {
              if (item.enabled) {
                onAction(item.id, node);
                onClose();
              }
            }}
            disabled={!item.enabled}
            className={`
              w-full flex items-center gap-3 px-3 py-2 text-sm
              ${item.enabled
                ? 'text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700'
                : 'text-surface-400 dark:text-surface-500 cursor-not-allowed'
              }
              transition-colors
            `}
          >
            <item.icon className="w-4 h-4" />
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export default function CKGEConsole() {
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [queryResults, setQueryResults] = useState(null);
  const [isQuerying, setIsQuerying] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [showFilters, setShowFilters] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);
  const [nodeFilters, setNodeFilters] = useState({
    file: true,
    class: true,
    function: true,
    dependency: true,
    vulnerability: true,
  });
  const { toast } = useToast();

  // File viewer state
  const [fileViewerOpen, setFileViewerOpen] = useState(false);
  const [fileViewerFile, setFileViewerFile] = useState(null);
  const [highlightedLines, setHighlightedLines] = useState([]);

  // Context menu state
  const [contextMenu, setContextMenu] = useState({ position: null, node: null });

  // Load data
  useEffect(() => {
    const timer = setTimeout(() => {
      setNodes(MOCK_NODES);
      setEdges(MOCK_EDGES);
      setLoading(false);
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  // Refresh handler
  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Simulate data refresh
    await new Promise((resolve) => setTimeout(resolve, 800));
    setNodes(MOCK_NODES);
    setEdges(MOCK_EDGES);
    setIsRefreshing(false);
    toast.success('Knowledge Graph refreshed');
  };

  // Fullscreen keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'f' || e.key === 'F') {
        if (!isFullscreen && !e.target.matches('input, textarea')) {
          setIsFullscreen(true);
        }
      }
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);

  // Filter nodes based on type filters
  const filteredNodes = nodes.filter(node => nodeFilters[node.type]);
  const filteredEdges = edges.filter(edge =>
    filteredNodes.some(n => n.id === edge.source) &&
    filteredNodes.some(n => n.id === edge.target)
  );

  // Handle query execution
  const handleQueryExecute = async (query) => {
    setIsQuerying(true);
    // Simulate query execution
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Simple mock query matching
    let results = [];
    const lowerQuery = query.toLowerCase();

    if (lowerQuery.includes('vulnerability') || lowerQuery.includes('cve')) {
      results = nodes.filter(n => n.type === 'vulnerability');
    } else if (lowerQuery.includes('class')) {
      results = nodes.filter(n => n.type === 'class');
    } else if (lowerQuery.includes('function') || lowerQuery.includes('complexity')) {
      results = nodes.filter(n => n.type === 'function');
    } else if (lowerQuery.includes('dependency')) {
      results = nodes.filter(n => n.type === 'dependency');
    } else {
      results = nodes.slice(0, 5);
    }

    setQueryResults(results);
    setIsQuerying(false);
  };

  // Zoom controls
  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 3));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.3));
  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // File viewer handlers
  const handleOpenFile = useCallback((node) => {
    if (node?.path) {
      // Map to mock file paths for development
      const mockPath = getMockFilePath(node.path);
      setFileViewerFile({ path: mockPath, line: node.line || 1 });
      setHighlightedLines(node.line ? [node.line] : []);
      setFileViewerOpen(true);
    }
  }, []);

  const handleCloseFileViewer = useCallback(() => {
    setFileViewerOpen(false);
    setFileViewerFile(null);
    setHighlightedLines([]);
  }, []);

  // Helper to map node paths to mock file paths
  const getMockFilePath = (path) => {
    // Map common patterns to our mock data
    if (path.includes('auth') || path.includes('login')) {
      return 'src/auth/handlers/login.py';
    }
    if (path.includes('user') || path.includes('User')) {
      return 'src/api/routes/users.js';
    }
    return path;
  };

  // Handle node double-click to open file
  const handleNodeDoubleClick = useCallback((node) => {
    if (node && (node.type === 'file' || node.type === 'class' || node.type === 'function')) {
      handleOpenFile(node);
    }
  }, [handleOpenFile]);

  // Handle context menu actions
  const handleContextMenuAction = useCallback((action, node) => {
    switch (action) {
      case 'viewFile':
        handleOpenFile(node);
        break;
      case 'viewReferences':
        // TODO: Implement reference viewing in graph
        break;
      case 'copyPath':
        if (node?.path) {
          navigator.clipboard.writeText(node.path);
        }
        break;
      case 'openInIDE':
        // TODO: Implement IDE integration
        break;
      default:
        break;
    }
  }, [handleOpenFile]);

  // Handle right-click context menu
  const handleGraphContextMenu = useCallback((e, node) => {
    setContextMenu({
      position: { x: e.clientX, y: e.clientY },
      node,
    });
  }, []);

  const handleCloseContextMenu = useCallback(() => {
    setContextMenu({ position: null, node: null });
  }, []);

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="p-6 bg-white dark:bg-surface-800 backdrop-blur-xl border-b border-surface-200/50 dark:border-surface-700/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-olive-100 dark:bg-olive-900/30 rounded-lg">
              <ShareIcon className="w-6 h-6 text-olive-600 dark:text-olive-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                Knowledge Graph
              </h1>
              <p className="text-surface-500 dark:text-surface-400">
                Explore and query your codebase relationships
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <ArrowPathIcon className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                showFilters
                  ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400'
                  : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'
              }`}
            >
              <AdjustmentsHorizontalIcon className="w-4 h-4" />
              Filters
            </button>
            <button
              onClick={() => setIsFullscreen(true)}
              className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              title="Expand to fullscreen (F)"
            >
              <ArrowsPointingOutIcon className="w-4 h-4" />
              Expand
            </button>
          </div>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="mt-4 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
            <p className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-3">Node Types</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(NODE_TYPES).map(([key, config]) => (
                <button
                  key={key}
                  onClick={() => setNodeFilters(f => ({ ...f, [key]: !f[key] }))}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    nodeFilters[key]
                      ? 'bg-white dark:bg-surface-800 border-2 shadow-sm'
                      : 'bg-surface-100 dark:bg-surface-600 opacity-50'
                  }`}
                  style={{ borderColor: nodeFilters[key] ? config.color : 'transparent' }}
                >
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: config.color }}
                  />
                  {config.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Graph Canvas (70%) */}
        <div className="flex-1 relative">
          <GraphCanvas
            nodes={filteredNodes}
            edges={filteredEdges}
            selectedNode={selectedNode}
            onNodeSelect={setSelectedNode}
            onNodeDoubleClick={handleNodeDoubleClick}
            onContextMenu={handleGraphContextMenu}
            zoom={zoom}
            pan={pan}
            onPanChange={setPan}
            onZoomChange={setZoom}
          />

          {/* Zoom Controls */}
          <div className="absolute bottom-4 left-4 flex flex-col gap-2 bg-white dark:bg-surface-800 rounded-lg shadow-lg border border-surface-200 dark:border-surface-700 p-1">
            <button
              onClick={handleZoomIn}
              className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded transition-colors"
            >
              <PlusIcon className="w-4 h-4 text-surface-600 dark:text-surface-400" />
            </button>
            <button
              onClick={handleZoomOut}
              className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded transition-colors"
            >
              <MinusIcon className="w-4 h-4 text-surface-600 dark:text-surface-400" />
            </button>
            <div className="border-t border-surface-200 dark:border-surface-700" />
            <button
              onClick={() => setIsFullscreen(true)}
              className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded transition-colors"
              title="Expand to fullscreen (F)"
            >
              <ArrowsPointingOutIcon className="w-4 h-4 text-surface-600 dark:text-surface-400" />
            </button>
          </div>

          {/* Zoom Level Indicator */}
          <div className="absolute bottom-4 right-4 bg-white dark:bg-surface-800 rounded-lg shadow-lg border border-surface-200 dark:border-surface-700 px-3 py-1.5">
            <span className="text-sm font-medium text-surface-600 dark:text-surface-400">
              {Math.round(zoom * 100)}%
            </span>
          </div>

          {/* Legend */}
          <div className="absolute top-4 left-4 bg-white dark:bg-surface-800 rounded-lg shadow-lg border border-surface-200 dark:border-surface-700 p-3">
            <p className="text-xs font-medium text-surface-500 dark:text-surface-400 mb-2">Legend</p>
            <div className="space-y-1.5">
              {Object.entries(NODE_TYPES).map(([key, config]) => (
                <div key={key} className="flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: config.color }}
                  />
                  <span className="text-xs text-surface-600 dark:text-surface-400">{config.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Query Panel (30%) */}
        <div className="w-[400px] flex-shrink-0 bg-white dark:bg-surface-800 border-l border-surface-200 dark:border-surface-700 flex flex-col overflow-hidden">
          {/* Query Builder */}
          <QueryBuilder onExecute={handleQueryExecute} isLoading={isQuerying} />

          {/* Selected Node Details */}
          <NodeDetailPanel
            node={selectedNode}
            edges={filteredEdges}
            nodes={filteredNodes}
            onClose={() => setSelectedNode(null)}
            onNodeClick={setSelectedNode}
            onCenterNode={handleResetView}
            onOpenFile={handleOpenFile}
          />

          {/* Query Results */}
          <div className="flex-1 overflow-y-auto">
            <QueryResults
              results={queryResults}
              onNodeClick={setSelectedNode}
            />
          </div>

          {/* Graph Metrics - positioned at bottom with clearance for chat button */}
          <div className="mb-24">
            <GraphMetrics nodes={filteredNodes} edges={filteredEdges} />
          </div>
        </div>

        {/* File Viewer Side Panel */}
        {fileViewerOpen && (
          <div className="w-[500px] flex-shrink-0 border-l border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 overflow-hidden">
            <FileViewer
              initialFile={fileViewerFile}
              highlightedLines={highlightedLines}
              onClose={handleCloseFileViewer}
              onLineClick={(_line) => {
                // TODO: Handle line click - navigate to code reference
              }}
            />
          </div>
        )}
      </div>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div
          className="fixed inset-0 z-50 bg-white dark:bg-surface-900 flex flex-col"
          style={{ animation: 'scaleIn 300ms ease-out' }}
        >
          {/* Fullscreen Header */}
          <div className="h-14 px-4 flex items-center justify-between border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800">
            <div className="flex items-center gap-3">
              <div className="p-1.5 bg-olive-100 dark:bg-olive-900/30 rounded-lg">
                <ShareIcon className="w-5 h-5 text-olive-600 dark:text-olive-400" />
              </div>
              <h2 className="font-semibold text-surface-900 dark:text-surface-100">
                Knowledge Graph
              </h2>
            </div>
            <button
              onClick={() => setIsFullscreen(false)}
              className="flex items-center gap-2 px-3 py-1.5 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              title="Exit fullscreen (Esc)"
            >
              <ArrowsPointingInIcon className="w-4 h-4" />
              <span className="text-sm">Exit</span>
            </button>
          </div>

          {/* Fullscreen Content */}
          <div className="flex-1 flex overflow-hidden">
            {/* Fullscreen Graph Canvas */}
            <div className="flex-1 relative">
              <GraphCanvas
                nodes={filteredNodes}
                edges={filteredEdges}
                selectedNode={selectedNode}
                onNodeSelect={setSelectedNode}
                onNodeDoubleClick={handleNodeDoubleClick}
                onContextMenu={handleGraphContextMenu}
                zoom={zoom}
                pan={pan}
                onPanChange={setPan}
                onZoomChange={setZoom}
              />

              {/* Legend (top-left) */}
              <div className="absolute top-4 left-4 bg-white dark:bg-surface-800 rounded-lg shadow-lg border border-surface-200 dark:border-surface-700 p-3">
                <p className="text-xs font-medium text-surface-500 dark:text-surface-400 mb-2">Legend</p>
                <div className="space-y-1.5">
                  {Object.entries(NODE_TYPES).map(([key, config]) => (
                    <div key={key} className="flex items-center gap-2">
                      <span
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: config.color }}
                      />
                      <span className="text-xs text-surface-600 dark:text-surface-400">{config.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Collapsible Panel */}
            <div
              className={`relative border-l border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 transition-all duration-300 ease-in-out ${
                isPanelCollapsed ? 'w-12' : 'w-[360px]'
              }`}
            >
              {/* Panel Toggle Button */}
              <button
                onClick={() => setIsPanelCollapsed(!isPanelCollapsed)}
                className="absolute top-4 -left-3 z-10 p-1 bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-full shadow-md hover:bg-surface-50 dark:hover:bg-surface-700 transition-colors"
              >
                {isPanelCollapsed ? (
                  <ChevronLeftIcon className="w-4 h-4 text-surface-500" />
                ) : (
                  <ChevronRightIcon className="w-4 h-4 text-surface-500" />
                )}
              </button>

              {/* Panel Content */}
              {!isPanelCollapsed && (
                <div className="h-full flex flex-col overflow-hidden">
                  <QueryBuilder onExecute={handleQueryExecute} isLoading={isQuerying} />
                  <NodeDetailPanel
                    node={selectedNode}
                    edges={filteredEdges}
                    nodes={filteredNodes}
                    onClose={() => setSelectedNode(null)}
                    onNodeClick={setSelectedNode}
                    onCenterNode={handleResetView}
                    onOpenFile={handleOpenFile}
                  />
                  <div className="flex-1 overflow-y-auto">
                    <QueryResults
                      results={queryResults}
                      onNodeClick={setSelectedNode}
                    />
                  </div>
                  {/* Graph Metrics - positioned at bottom with clearance for chat button */}
                  <div className="mb-24">
                    <GraphMetrics nodes={filteredNodes} edges={filteredEdges} />
                  </div>
                </div>
              )}
            </div>

            {/* File Viewer in Fullscreen */}
            {fileViewerOpen && (
              <div className="w-[500px] flex-shrink-0 border-l border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 overflow-hidden">
                <FileViewer
                  initialFile={fileViewerFile}
                  highlightedLines={highlightedLines}
                  onClose={handleCloseFileViewer}
                  onLineClick={(_line) => {
                // TODO: Handle line click - navigate to code reference
              }}
                />
              </div>
            )}
          </div>

          {/* Fullscreen Bottom Control Bar */}
          <div className="h-14 px-4 flex items-center justify-between border-t border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800">
            {/* Zoom Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleZoomOut}
                className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              >
                <MinusIcon className="w-4 h-4 text-surface-600 dark:text-surface-400" />
              </button>
              <span className="text-sm font-medium text-surface-600 dark:text-surface-400 w-14 text-center">
                {Math.round(zoom * 100)}%
              </span>
              <button
                onClick={handleZoomIn}
                className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              >
                <PlusIcon className="w-4 h-4 text-surface-600 dark:text-surface-400" />
              </button>
              <button
                onClick={handleResetView}
                className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors ml-2"
                title="Reset view"
              >
                <ArrowsPointingOutIcon className="w-4 h-4 text-surface-600 dark:text-surface-400" />
              </button>
            </div>

            {/* Keyboard Hint */}
            <span className="text-xs text-surface-400">
              Press <kbd className="px-1.5 py-0.5 bg-surface-100 dark:bg-surface-700 rounded text-surface-500">Esc</kbd> to exit fullscreen
            </span>
          </div>
        </div>
      )}

      {/* Context Menu */}
      <NodeContextMenu
        position={contextMenu.position}
        node={contextMenu.node}
        onAction={handleContextMenuAction}
        onClose={handleCloseContextMenu}
      />

      {/* CSS Animation for Fullscreen */}
      <style>{`
        @keyframes scaleIn {
          from {
            opacity: 0;
            transform: scale(0.98);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }
      `}</style>
    </div>
  );
}
