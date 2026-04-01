/**
 * Project Aura - CapabilityGraph Component
 *
 * Interactive force-directed graph visualization for agent capabilities.
 * Implements ADR-071 for Cross-Agent Capability Graph Analysis.
 *
 * Visual design matches KnowledgeGraph.jsx for consistency:
 * - Dark background with subtle grid pattern
 * - Opaque fill nodes with colored stroke ring borders
 * - Selection ring with animated dashed pattern
 * - Hover glow effect
 * - Clean label positioning below nodes
 *
 * Features:
 * - Force-directed layout with drag interaction
 * - Color-coded nodes by classification
 * - Escalation path highlighting
 * - Zoom and pan controls
 * - Node details on hover/click
 *
 * @author Project Aura Team
 * @created 2026-01-27
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  MagnifyingGlassPlusIcon,
  MagnifyingGlassMinusIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline';
import { useCapabilityGraph } from './useCapabilityGraph';

// ============================================================================
// Constants & Configuration (matching Knowledge Graph styling)
// ============================================================================

// Node colors by classification - used for stroke rings
const NODE_COLORS = {
  agent: '#3B82F6',      // Blue - Aura brand color
  safe: '#10B981',       // Green
  monitoring: '#F59E0B', // Amber
  dangerous: '#EA580C',  // Orange
  critical: '#DC2626',   // Red
  default: '#6B7280',    // Gray
};

// Node radii - significantly larger for better readability
const NODE_RADII = {
  agent: 30,             // Agents are prominent (was ~20-24)
  tool: 20,              // Tools are smaller but still readable (was ~12-14)
};

// Classification abbreviations for tool nodes
const CLASSIFICATION_ABBREV = {
  safe: 'S',
  monitoring: 'M',
  dangerous: 'D',
  critical: 'C',
};

// Agent type abbreviations
const AGENT_TYPE_ABBREV = {
  coder: 'Coder',
  reviewer: 'Review',
  validator: 'Valid',
  security: 'Secur',
  orchestrator: 'Orch',
  patcher: 'Patch',
};

// Edge styles by relationship type (matching Knowledge Graph)
const EDGE_TYPES = {
  HAS_CAPABILITY: {
    color: '#64748B',      // Slate gray - standard capability link
    dashed: false,
  },
  DELEGATES_TO: {
    color: '#F59E0B',      // Amber - delegation
    dashed: true,
  },
  INHERITS_FROM: {
    color: '#A78BFA',      // Purple - inheritance
    dashed: true,
  },
  ESCALATION: {
    color: '#EF4444',      // Red - escalation path
    dashed: false,
  },
  default: {
    color: '#475569',      // Darker slate for default
    dashed: false,
  },
};

// ============================================================================
// Force Simulation (D3-inspired)
// ============================================================================

/**
 * D3-inspired force simulation for node positioning
 * Prevents node overlap with proper repulsion physics
 */
function useForceSimulation(nodes, edges, width, height) {
  const [positions, setPositions] = useState({});
  const animationRef = useRef(null);
  const nodeDataRef = useRef([]);

  useEffect(() => {
    if (!nodes.length) return;

    // Simulation parameters (tuned for readable spacing)
    const chargeStrength = -800;       // Strong repulsion to prevent clustering
    const linkDistance = 200;          // Longer ideal distance for readability
    const linkStrength = 0.2;          // Weaker links allow more spread
    const centerStrength = 0.02;       // Gentle pull towards center
    const collisionRadius = 90;        // Minimum distance between node centers
    const velocityDecay = 0.55;        // Friction (0-1)

    // Initialize node positions in a spread pattern
    const nodeData = nodes.map((node, i) => {
      // Spread nodes in concentric circles by type
      const isAgent = node.type === 'agent';
      const nodeRadius = isAgent ? NODE_RADII.agent : NODE_RADII.tool;
      // Wider initial spread for better separation
      const baseRadius = isAgent ? Math.min(width, height) * 0.3 : Math.min(width, height) * 0.45;
      const angleOffset = isAgent ? 0 : Math.PI / nodes.length;
      const angle = angleOffset + (2 * Math.PI * i) / nodes.length;

      return {
        id: node.id,
        x: width / 2 + baseRadius * Math.cos(angle) + (Math.random() - 0.5) * 80,
        y: height / 2 + baseRadius * Math.sin(angle) + (Math.random() - 0.5) * 80,
        vx: 0,
        vy: 0,
        type: node.type,
        radius: nodeRadius,
      };
    });

    nodeDataRef.current = nodeData;

    // Create edge lookup for link forces
    const edgeList = edges.map(edge => ({
      source: nodeData.find(n => n.id === edge.source),
      target: nodeData.find(n => n.id === edge.target),
    })).filter(e => e.source && e.target);

    // Simulation loop
    let iterations = 0;
    const maxIterations = 200;

    const simulate = () => {
      if (iterations >= maxIterations) {
        // Final positions
        const finalPositions = {};
        nodeData.forEach(node => {
          finalPositions[node.id] = { x: node.x, y: node.y };
        });
        setPositions(finalPositions);
        return;
      }

      const alpha = Math.max(0.1, 1 - iterations / maxIterations);

      // Apply center force
      nodeData.forEach(node => {
        node.vx += (width / 2 - node.x) * centerStrength * alpha;
        node.vy += (height / 2 - node.y) * centerStrength * alpha;
      });

      // Apply charge force (repulsion between all nodes)
      for (let i = 0; i < nodeData.length; i++) {
        for (let j = i + 1; j < nodeData.length; j++) {
          const nodeA = nodeData[i];
          const nodeB = nodeData[j];

          const dx = nodeB.x - nodeA.x;
          const dy = nodeB.y - nodeA.y;
          const distance = Math.sqrt(dx * dx + dy * dy) || 1;

          // Stronger repulsion when nodes are close
          const force = (chargeStrength * alpha) / (distance * distance);
          const fx = (dx / distance) * force;
          const fy = (dy / distance) * force;

          nodeA.vx -= fx;
          nodeA.vy -= fy;
          nodeB.vx += fx;
          nodeB.vy += fy;
        }
      }

      // Apply collision force (hard boundary to prevent overlap)
      for (let i = 0; i < nodeData.length; i++) {
        for (let j = i + 1; j < nodeData.length; j++) {
          const nodeA = nodeData[i];
          const nodeB = nodeData[j];

          const dx = nodeB.x - nodeA.x;
          const dy = nodeB.y - nodeA.y;
          const distance = Math.sqrt(dx * dx + dy * dy) || 1;
          const minDist = collisionRadius + nodeA.radius + nodeB.radius;

          if (distance < minDist) {
            const overlap = (minDist - distance) / 2;
            const pushX = (dx / distance) * overlap;
            const pushY = (dy / distance) * overlap;

            nodeA.x -= pushX;
            nodeA.y -= pushY;
            nodeB.x += pushX;
            nodeB.y += pushY;
          }
        }
      }

      // Apply link force (attraction between connected nodes)
      edgeList.forEach(edge => {
        const dx = edge.target.x - edge.source.x;
        const dy = edge.target.y - edge.source.y;
        const distance = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = ((distance - linkDistance) * linkStrength * alpha) / distance;

        const fx = dx * force;
        const fy = dy * force;

        edge.source.vx += fx;
        edge.source.vy += fy;
        edge.target.vx -= fx;
        edge.target.vy -= fy;
      });

      // Update positions with velocity
      const padding = 60;
      nodeData.forEach(node => {
        node.vx *= velocityDecay;
        node.vy *= velocityDecay;
        node.x += node.vx;
        node.y += node.vy;

        // Keep within bounds
        node.x = Math.max(padding, Math.min(width - padding, node.x));
        node.y = Math.max(padding, Math.min(height - padding, node.y));
      });

      // Update React state periodically (not every frame for performance)
      if (iterations % 5 === 0 || iterations === maxIterations - 1) {
        const currentPositions = {};
        nodeData.forEach(node => {
          currentPositions[node.id] = { x: node.x, y: node.y };
        });
        setPositions(currentPositions);
      }

      iterations++;
      animationRef.current = requestAnimationFrame(simulate);
    };

    animationRef.current = requestAnimationFrame(simulate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [nodes, edges, width, height]);

  return positions;
}

/**
 * CapabilityGraph Component
 */
export function CapabilityGraph({
  width = 800,
  height = 600,
  className = '',
  onNodeClick,
  showControls = true,
  showLegend = true,
  filters = {},
}) {
  const { data, loading, error, refresh } = useCapabilityGraph();

  // Extract filter values with defaults
  const {
    agentTypes = [],
    classifications = ['safe', 'monitoring', 'dangerous', 'critical'],
    showEscalationPaths = true,
    showCoverageGaps = false,
    showToxicCombinations = false,
    riskThreshold = 0.5,
  } = filters;
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const svgRef = useRef(null);
  const containerRef = useRef(null);

  // Parse nodes and edges from data, apply filters, add display labels
  const { nodes, edges, coverageGapAgents, toxicCombinationNodes, escalationPathEdges } = useMemo(() => {
    if (!data) return { nodes: [], edges: [], coverageGapAgents: new Set(), toxicCombinationNodes: new Set(), escalationPathEdges: new Set() };

    const rawNodes = data.nodes || [];
    const rawEdges = data.edges || [];
    const escalationPaths = data.escalation_paths || [];

    // =========================================================================
    // Step 1: Apply Agent Type Filter
    // =========================================================================
    // Filter agents by type if agentTypes array is not empty
    const agentTypeFiltered = rawNodes.filter(node => {
      if (node.type !== 'agent') return true; // Keep all non-agent nodes for now
      // If no agent types selected (empty array), show all agents
      if (agentTypes.length === 0) return true;
      // Otherwise, filter by selected agent types
      const nodeAgentType = node.agent_type || node.name?.toLowerCase().replace('agent', '') || '';
      return agentTypes.includes(nodeAgentType);
    });

    // =========================================================================
    // Step 2: Apply Tool Classification Filter
    // =========================================================================
    // Filter tools by classification
    const classificationFiltered = agentTypeFiltered.filter(node => {
      if (node.type === 'agent') return true; // Keep all agents
      // Filter tools by selected classifications
      return classifications.includes(node.classification);
    });

    // Get IDs of all remaining nodes for edge filtering
    const remainingNodeIds = new Set(classificationFiltered.map(n => n.id));

    // =========================================================================
    // Step 3: Filter Edges (only keep edges where both source and target exist)
    // =========================================================================
    const filteredEdges = rawEdges.filter(edge => {
      return remainingNodeIds.has(edge.source) && remainingNodeIds.has(edge.target);
    });

    // =========================================================================
    // Step 4: Remove Isolated Nodes (nodes with no connections after filtering)
    // =========================================================================
    const connectedNodeIds = new Set();
    filteredEdges.forEach(edge => {
      connectedNodeIds.add(edge.source);
      connectedNodeIds.add(edge.target);
    });
    const connectedNodes = classificationFiltered.filter(node => connectedNodeIds.has(node.id));

    // =========================================================================
    // Step 5: Identify Coverage Gaps (agents with DANGEROUS but no MONITORING)
    // =========================================================================
    const coverageGapAgentIds = new Set();
    if (showCoverageGaps) {
      // For each agent, check if they have dangerous tools but no monitoring tools
      const agentNodes = connectedNodes.filter(n => n.type === 'agent');
      agentNodes.forEach(agent => {
        // Find all tools connected to this agent
        const agentToolIds = filteredEdges
          .filter(e => e.source === agent.id && e.type === 'HAS_CAPABILITY')
          .map(e => e.target);
        const agentTools = connectedNodes.filter(n => agentToolIds.includes(n.id));

        const hasDangerous = agentTools.some(t => t.classification === 'dangerous' || t.classification === 'critical');
        const hasMonitoring = agentTools.some(t => t.classification === 'monitoring');

        // Coverage gap: has dangerous capabilities but no monitoring
        if (hasDangerous && !hasMonitoring) {
          coverageGapAgentIds.add(agent.id);
        }
      });
    }

    // =========================================================================
    // Step 6: Identify Toxic Combinations
    // =========================================================================
    const toxicNodeIds = new Set();
    const TOXIC_PAIRS = [
      ['deployment', 'database_access'],
      ['iam_modify', 'production_access'],
      ['secrets_manager', 'deployment'],
      ['file_write', 'production_access'],
    ];

    if (showToxicCombinations) {
      // For each agent, check if they have toxic tool combinations
      const agentNodes = connectedNodes.filter(n => n.type === 'agent');
      agentNodes.forEach(agent => {
        const agentToolIds = filteredEdges
          .filter(e => e.source === agent.id && e.type === 'HAS_CAPABILITY')
          .map(e => e.target);
        const agentTools = connectedNodes.filter(n => agentToolIds.includes(n.id));
        const toolNames = agentTools.map(t => t.name);

        // Check for toxic pairs
        for (const [tool1, tool2] of TOXIC_PAIRS) {
          if (toolNames.includes(tool1) && toolNames.includes(tool2)) {
            // Mark both tools as toxic
            const toxicTool1 = agentTools.find(t => t.name === tool1);
            const toxicTool2 = agentTools.find(t => t.name === tool2);
            if (toxicTool1) toxicNodeIds.add(toxicTool1.id);
            if (toxicTool2) toxicNodeIds.add(toxicTool2.id);
            // Also mark the agent
            toxicNodeIds.add(agent.id);
          }
        }
      });
    }

    // =========================================================================
    // Step 7: Identify Escalation Path Edges (filtered by risk threshold)
    // =========================================================================
    const escalationEdgeIndices = new Set();
    if (showEscalationPaths) {
      // Filter escalation paths by risk threshold
      const relevantPaths = escalationPaths.filter(p => p.risk_score >= riskThreshold);

      // Build a set of node pairs that are part of escalation paths
      const escalationPairs = new Set();
      relevantPaths.forEach(path => {
        const pathNodes = path.path || [];
        for (let i = 0; i < pathNodes.length - 1; i++) {
          // Create both directions for lookup
          escalationPairs.add(`${pathNodes[i]}:${pathNodes[i + 1]}`);
          escalationPairs.add(`${pathNodes[i + 1]}:${pathNodes[i]}`);
        }
      });

      // Mark edges that are part of escalation paths
      filteredEdges.forEach((edge, i) => {
        const pairKey1 = `${edge.source}:${edge.target}`;
        const pairKey2 = `${edge.target}:${edge.source}`;
        if (escalationPairs.has(pairKey1) || escalationPairs.has(pairKey2)) {
          escalationEdgeIndices.add(i);
        }
      });

      // Also mark edges connected to nodes with has_escalation_risk flag
      filteredEdges.forEach((edge, i) => {
        const sourceNode = connectedNodes.find(n => n.id === edge.source);
        const targetNode = connectedNodes.find(n => n.id === edge.target);
        if ((sourceNode?.has_escalation_risk || targetNode?.has_escalation_risk) &&
            (sourceNode?.classification === 'critical' || targetNode?.classification === 'critical')) {
          escalationEdgeIndices.add(i);
        }
      });
    }

    // =========================================================================
    // Step 8: Count agents by type for numbering (e.g., Coder1, Coder2)
    // =========================================================================
    const agentTypeCounts = {};
    connectedNodes.forEach(node => {
      if (node.type === 'agent') {
        const agentType = node.agent_type || node.name?.toLowerCase().replace('agent', '') || 'agent';
        agentTypeCounts[agentType] = (agentTypeCounts[agentType] || 0) + 1;
      }
    });

    // =========================================================================
    // Step 9: Assign Display Labels
    // =========================================================================
    const typeCounters = {};
    const labeledNodes = connectedNodes.map(node => {
      if (node.type === 'agent') {
        const agentType = node.agent_type || node.name?.toLowerCase().replace('agent', '') || 'agent';
        typeCounters[agentType] = (typeCounters[agentType] || 0) + 1;
        const instanceNum = typeCounters[agentType];
        const abbrev = AGENT_TYPE_ABBREV[agentType] || agentType.charAt(0).toUpperCase() + agentType.slice(1, 5);
        // Show number only if multiple agents of same type
        const displayLabel = agentTypeCounts[agentType] > 1
          ? `${abbrev}${instanceNum}`
          : abbrev;

        // Add coverage gap and toxic combination flags
        return {
          ...node,
          displayLabel,
          label: node.label || node.name,
          hasCoverageGap: coverageGapAgentIds.has(node.id),
          isToxicCombination: toxicNodeIds.has(node.id),
        };
      } else {
        // Tool nodes get classification abbreviation
        const classAbbrev = CLASSIFICATION_ABBREV[node.classification] || '?';
        return {
          ...node,
          displayLabel: classAbbrev,
          label: node.label || node.name,
          isToxicCombination: toxicNodeIds.has(node.id),
        };
      }
    });

    return {
      nodes: labeledNodes,
      edges: filteredEdges,
      coverageGapAgents: coverageGapAgentIds,
      toxicCombinationNodes: toxicNodeIds,
      escalationPathEdges: escalationEdgeIndices,
    };
  }, [data, agentTypes, classifications, showEscalationPaths, showCoverageGaps, showToxicCombinations, riskThreshold]);

  // Calculate positions
  const positions = useForceSimulation(nodes, edges, width, height);

  // Handle zoom
  const handleZoomIn = useCallback(() => {
    setZoom((z) => Math.min(z * 1.2, 3));
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoom((z) => Math.max(z / 1.2, 0.5));
  }, []);

  const handleZoomReset = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  // Handle canvas pan (drag to move entire graph)
  const handleCanvasPan = useCallback((e) => {
    if (e.buttons !== 1) return;

    setPan((prev) => ({
      x: prev.x + e.movementX,
      y: prev.y + e.movementY,
    }));
  }, []);

  // Handle mouse wheel zoom
  const handleWheel = useCallback((e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((prev) => Math.max(0.5, Math.min(3, prev * delta)));
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

  // Handle node click
  const handleNodeClick = useCallback(
    (node) => {
      setSelectedNode(node.id === selectedNode ? null : node.id);
      onNodeClick?.(node);
    },
    [selectedNode, onNodeClick]
  );

  // Get node stroke color (for ring border - matching Knowledge Graph pattern)
  const getNodeColor = useCallback((node) => {
    if (node.type === 'agent') {
      return node.has_escalation_risk ? NODE_COLORS.critical : NODE_COLORS.agent;
    }
    return NODE_COLORS[node.classification] || NODE_COLORS.default;
  }, []);

  // Get node radius - larger sizes for better readability
  const getNodeRadius = useCallback((node) => {
    if (node.type === 'agent') {
      // Base radius of 30, plus slight scaling for capability count (max +6)
      return NODE_RADII.agent + Math.min(node.capabilities_count || 0, 6);
    }
    return NODE_RADII.tool;
  }, []);

  // Calculate connected nodes for focus mode (dims unrelated nodes when hovering/selecting)
  const { connectedNodes, connectedEdges, hasActiveNode } = useMemo(() => {
    const activeNodeId = hoveredNode || selectedNode;
    if (!activeNodeId) {
      return { connectedNodes: new Set(), connectedEdges: new Set(), hasActiveNode: false };
    }

    const connected = new Set([activeNodeId]);
    const connectedEdgeIds = new Set();

    edges.forEach((edge, i) => {
      if (edge.source === activeNodeId || edge.target === activeNodeId) {
        connected.add(edge.source);
        connected.add(edge.target);
        connectedEdgeIds.add(i);
      }
    });

    return {
      connectedNodes: connected,
      connectedEdges: connectedEdgeIds,
      hasActiveNode: true,
    };
  }, [hoveredNode, selectedNode, edges]);

  // Render loading state
  if (loading) {
    return (
      <div className={`flex items-center justify-center ${className}`} style={{ width, height }}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto" />
          <p className="mt-4 text-gray-400">Loading capability graph...</p>
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className={`flex items-center justify-center ${className}`} style={{ width, height }}>
        <div className="text-center text-red-400">
          <ExclamationTriangleIcon className="h-12 w-12 mx-auto mb-4" />
          <p>Failed to load graph: {error}</p>
          <button
            onClick={refresh}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Render empty state
  if (!nodes.length) {
    return (
      <div className={`flex items-center justify-center ${className}`} style={{ width, height }}>
        <div className="text-center text-gray-400">
          <ShieldCheckIcon className="h-12 w-12 mx-auto mb-4" />
          <p>No capability data available</p>
          <button
            onClick={refresh}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Sync Policies
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative bg-slate-900 rounded-lg ${className} ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}
      style={isFullscreen ? { width: '100vw', height: '100vh', borderRadius: 0 } : undefined}
      onMouseMove={(e) => {
        if (isDragging) handleCanvasPan(e);
      }}
      onMouseUp={() => setIsDragging(false)}
      onMouseLeave={() => setIsDragging(false)}
    >
      {/* Controls - styled like Knowledge Graph */}
      {showControls && (
        <div className="absolute bottom-4 right-4 flex flex-col gap-1 bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-xl shadow-lg border border-surface-700/50 p-1 z-10">
          <button
            onClick={handleZoomIn}
            className="p-2 rounded-lg hover:bg-surface-700 transition-all duration-200"
            aria-label="Zoom in"
            title="Zoom in"
          >
            <MagnifyingGlassPlusIcon className="w-5 h-5 text-surface-400" />
          </button>

          <div className="text-center text-xs text-surface-500 py-1">
            {Math.round(zoom * 100)}%
          </div>

          <button
            onClick={handleZoomOut}
            className="p-2 rounded-lg hover:bg-surface-700 transition-all duration-200"
            aria-label="Zoom out"
            title="Zoom out"
          >
            <MagnifyingGlassMinusIcon className="w-5 h-5 text-surface-400" />
          </button>

          <div className="border-t border-surface-700/50 my-1" />

          <button
            onClick={handleToggleFullscreen}
            className="p-2 rounded-lg hover:bg-surface-700 transition-all duration-200"
            aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? (
              <ArrowsPointingInIcon className="w-5 h-5 text-surface-400" />
            ) : (
              <ArrowsPointingOutIcon className="w-5 h-5 text-surface-400" />
            )}
          </button>

          <button
            onClick={refresh}
            className="p-2 rounded-lg hover:bg-surface-700 transition-all duration-200"
            aria-label="Refresh graph"
            title="Refresh"
          >
            <ArrowPathIcon className="w-5 h-5 text-surface-400" />
          </button>
        </div>
      )}

      {/* Legend - fixed bottom-left to avoid popup overlap */}
      {showLegend && (
        <div className="absolute bottom-4 left-4 bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-xl shadow-lg border border-surface-700/50 p-3 z-10 max-w-[200px]">
          <p className="text-xs font-medium text-surface-400 mb-2">
            Node Types
          </p>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div
                className="w-3.5 h-3.5 rounded-full flex-shrink-0"
                style={{ border: `2px solid ${NODE_COLORS.agent}`, backgroundColor: '#1e293b' }}
              />
              <span className="text-xs text-surface-300">Agent</span>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="w-3.5 h-3.5 rounded-full flex-shrink-0"
                style={{ border: `2px solid ${NODE_COLORS.safe}`, backgroundColor: '#1e293b' }}
              />
              <span className="text-xs text-surface-300">Safe Tool</span>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="w-3.5 h-3.5 rounded-full flex-shrink-0"
                style={{ border: `2px solid ${NODE_COLORS.monitoring}`, backgroundColor: '#1e293b' }}
              />
              <span className="text-xs text-surface-300">Monitoring</span>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="w-3.5 h-3.5 rounded-full flex-shrink-0"
                style={{ border: `2px solid ${NODE_COLORS.dangerous}`, backgroundColor: '#1e293b' }}
              />
              <span className="text-xs text-surface-300">Dangerous</span>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="w-3.5 h-3.5 rounded-full flex-shrink-0"
                style={{ border: `2px solid ${NODE_COLORS.critical}`, backgroundColor: '#1e293b' }}
              />
              <span className="text-xs text-surface-300">Critical</span>
            </div>
          </div>

          {/* Indicators section - shown when relevant filters are active */}
          {(showEscalationPaths || showCoverageGaps || showToxicCombinations) && (
            <>
              <div className="border-t border-surface-700/50 my-2" />
              <p className="text-xs font-medium text-surface-400 mb-2">
                Indicators
              </p>
              <div className="space-y-1.5">
                {showEscalationPaths && (
                  <div className="flex items-center gap-2">
                    <div className="w-3.5 h-0.5 flex-shrink-0 bg-red-500" />
                    <span className="text-xs text-surface-300">Escalation Path</span>
                  </div>
                )}
                {showCoverageGaps && (
                  <div className="flex items-center gap-2">
                    <div className="w-3.5 h-3.5 rounded-full flex-shrink-0 bg-amber-500 flex items-center justify-center">
                      <span className="text-[8px] text-white font-bold">?</span>
                    </div>
                    <span className="text-xs text-surface-300">Coverage Gap</span>
                  </div>
                )}
                {showToxicCombinations && (
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3.5 h-3.5 rounded-full flex-shrink-0"
                      style={{ border: '2px dashed #DC2626', backgroundColor: 'transparent' }}
                    />
                    <span className="text-xs text-surface-300">Toxic Combo</span>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* SVG Graph - styled to match Knowledge Graph */}
      <svg
        ref={svgRef}
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={`${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
        preserveAspectRatio="xMidYMid slice"
        onMouseDown={(e) => {
          // Only start dragging if clicking on the background (not on nodes)
          if (e.target === svgRef.current || e.target.tagName === 'rect' || e.target.tagName === 'svg') {
            setIsDragging(true);
            setSelectedNode(null);
          }
        }}
        onWheel={handleWheel}
      >
        {/* Defs for patterns and markers */}
        <defs>
          {/* Background grid pattern - subtle blue tint matching Knowledge Graph */}
          <pattern id="capability-grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path
              d="M 24 0 L 0 0 0 24"
              fill="none"
              stroke="rgba(59, 130, 246, 0.08)"
              strokeWidth="0.5"
            />
          </pattern>

          {/* Arrow marker for edges - with dark outline */}
          <marker
            id="capability-arrowhead"
            markerWidth="12"
            markerHeight="9"
            refX="10"
            refY="4.5"
            orient="auto"
          >
            <polygon points="-1 -1, 12 4.5, -1 10" fill="#0f172a" />
            <polygon points="0 0, 10 4.5, 0 9" fill="#64748B" />
          </marker>

          {/* Highlighted arrow marker - with dark outline */}
          <marker
            id="capability-arrowhead-highlight"
            markerWidth="12"
            markerHeight="9"
            refX="10"
            refY="4.5"
            orient="auto"
          >
            <polygon points="-1 -1, 12 4.5, -1 10" fill="#0f172a" />
            <polygon points="0 0, 10 4.5, 0 9" fill="#3B82F6" />
          </marker>

          {/* Escalation path arrow marker - red with dark outline */}
          <marker
            id="capability-arrowhead-escalation"
            markerWidth="12"
            markerHeight="9"
            refX="10"
            refY="4.5"
            orient="auto"
          >
            <polygon points="-1 -1, 12 4.5, -1 10" fill="#0f172a" />
            <polygon points="0 0, 10 4.5, 0 9" fill="#EF4444" />
          </marker>
        </defs>

        {/* Solid dark background first - extra wide to fill container */}
        <rect x="-500" width={width + 1000} height={height} fill="#0f172a" />

        {/* Grid overlay - extra wide to fill container */}
        <rect x="-500" width={width + 1000} height={height} fill="url(#capability-grid)" />

        {/* Zoomable and pannable content group */}
        <g
          transform={`translate(${pan.x + width / 2}, ${pan.y + height / 2}) scale(${zoom}) translate(${-width / 2}, ${-height / 2})`}
        >
        {/* Edges - smooth curved bezier paths like Knowledge Graph */}
        <g className="edges">
          {edges.map((edge, i) => {
            const sourcePos = positions[edge.source];
            const targetPos = positions[edge.target];
            if (!sourcePos || !targetPos) return null;

            // Get edge type configuration
            // Check if this edge is part of a detected escalation path
            const isEscalationEdge = escalationPathEdges.has(i);
            const edgeType = isEscalationEdge ? 'ESCALATION' : (edge.is_escalation_path ? 'ESCALATION' : (edge.type || 'HAS_CAPABILITY'));
            const config = EDGE_TYPES[edgeType] || EDGE_TYPES.default;

            // Calculate edge path
            const dx = targetPos.x - sourcePos.x;
            const dy = targetPos.y - sourcePos.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < 1) return null;

            // Get node radii for proper edge termination
            const sourceNode = nodes.find(n => n.id === edge.source);
            const targetNode = nodes.find(n => n.id === edge.target);
            const sourceRadius = getNodeRadius(sourceNode);
            const targetRadius = getNodeRadius(targetNode);

            // Check if this edge is connected to selected/hovered node
            const isHighlighted = (selectedNode === edge.source || selectedNode === edge.target ||
                                   hoveredNode === edge.source || hoveredNode === edge.target);

            // Check if this edge should be dimmed (not connected to active node)
            const isDimmed = hasActiveNode && !connectedEdges.has(i);

            // Calculate start and end points at node borders
            const startX = sourcePos.x + (dx / distance) * sourceRadius;
            const startY = sourcePos.y + (dy / distance) * sourceRadius;
            const endX = targetPos.x - (dx / distance) * (targetRadius + 8);
            const endY = targetPos.y - (dy / distance) * (targetRadius + 8);

            // Calculate control point for quadratic bezier curve
            // Perpendicular offset creates smooth arc
            const midX = (startX + endX) / 2;
            const midY = (startY + endY) / 2;

            // Perpendicular vector (normalized)
            const perpX = -dy / distance;
            const perpY = dx / distance;

            // Curve offset - varies by edge index to prevent overlapping
            // Use edge type to determine curve direction for visual distinction
            const curveOffset = edgeType === 'DELEGATES_TO' || edgeType === 'INHERITS_FROM'
              ? 25 + (i % 3) * 10
              : 20 + (i % 4) * 8;
            const curveDirection = i % 2 === 0 ? 1 : -1;

            // Control point
            const ctrlX = midX + perpX * curveOffset * curveDirection;
            const ctrlY = midY + perpY * curveOffset * curveDirection;

            // SVG quadratic bezier path
            const pathD = `M ${startX} ${startY} Q ${ctrlX} ${ctrlY} ${endX} ${endY}`;

            // Determine opacity: highlighted > normal > dimmed
            const edgeOpacity = isHighlighted ? 1 : isDimmed ? 0.15 : 0.7;

            return (
              <g key={`edge-${i}`} className="transition-opacity duration-200">
                {/* Dark outline stroke for edge separation */}
                <path
                  d={pathD}
                  fill="none"
                  stroke="#0f172a"
                  strokeWidth={isHighlighted ? 5.5 : 4}
                  strokeDasharray={config.dashed ? '6 3' : undefined}
                  opacity={edgeOpacity}
                  strokeLinecap="round"
                  style={{ transition: 'opacity 200ms ease-out' }}
                />
                {/* Main colored edge stroke */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={isEscalationEdge ? '#EF4444' : (isHighlighted ? '#3B82F6' : config.color)}
                  strokeWidth={isEscalationEdge ? 2.5 : (isHighlighted ? 2.5 : 1.5)}
                  strokeDasharray={config.dashed ? '6 3' : undefined}
                  markerEnd={isEscalationEdge ? 'url(#capability-arrowhead-escalation)' : (isHighlighted ? 'url(#capability-arrowhead-highlight)' : 'url(#capability-arrowhead)')}
                  opacity={edgeOpacity}
                  strokeLinecap="round"
                  style={{ transition: 'opacity 200ms ease-out' }}
                />
              </g>
            );
          })}
        </g>

        {/* Nodes - styled like Knowledge Graph with opaque fill + colored stroke ring */}
        <g className="nodes">
          {nodes.map((node) => {
            const pos = positions[node.id];
            if (!pos) return null;

            const radius = getNodeRadius(node);
            const color = getNodeColor(node);
            const isSelected = selectedNode === node.id;
            const isHovered = hoveredNode === node.id;
            const isActive = isSelected || isHovered;

            // Check if this node should be dimmed (not connected to active node)
            const isDimmed = hasActiveNode && !connectedNodes.has(node.id);
            const nodeOpacity = isActive ? 1 : isDimmed ? 0.35 : 1;

            return (
              <g
                key={node.id}
                transform={`translate(${pos.x}, ${pos.y})${isHovered ? ' scale(1.05)' : ''}`}
                onClick={() => handleNodeClick(node)}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                className="cursor-pointer"
                opacity={nodeOpacity}
                style={{ transition: 'opacity 200ms ease-out' }}
              >
                {/* Selection ring - dashed animated stroke (Knowledge Graph pattern) */}
                {isSelected && (
                  <circle
                    r={radius + 8}
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    strokeDasharray="4 2"
                    className="animate-pulse"
                  />
                )}

                {/* Hover glow - filled circle with low opacity (Knowledge Graph pattern) */}
                {isHovered && !isSelected && (
                  <circle
                    r={radius + 6}
                    fill={color}
                    opacity="0.2"
                    className="transition-opacity"
                  />
                )}

                {/* Main node circle - opaque fill with colored stroke ring */}
                <circle
                  r={radius}
                  fill="#1e293b"
                  stroke={color}
                  strokeWidth="4"
                />

                {/* Inner fill with classification color */}
                <circle
                  r={radius - 4}
                  fill={color}
                  opacity="0.25"
                />

                {/* Label inside node - Abbreviated identifier */}
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="#ffffff"
                  fontSize={node.type === 'agent' ? 12 : 11}
                  fontWeight="700"
                  className="select-none pointer-events-none"
                  style={{ fontFamily: 'Inter, system-ui, sans-serif', textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}
                >
                  {node.displayLabel}
                </text>

                {/* Full label below node with background for readability */}
                {(() => {
                  const labelText = node.label?.length > 16 ? node.label.substring(0, 13) + '...' : node.label;
                  const labelWidth = Math.max(labelText?.length * 6.5 || 50, 40);
                  const labelHeight = 16;
                  const labelY = radius + 14;

                  return (
                    <>
                      {/* Semi-transparent background for label */}
                      <rect
                        x={-labelWidth / 2 - 6}
                        y={labelY}
                        width={labelWidth + 12}
                        height={labelHeight}
                        rx="4"
                        ry="4"
                        fill="rgba(15, 23, 42, 0.75)"
                        className="pointer-events-none"
                      />
                      <text
                        y={labelY + labelHeight / 2}
                        textAnchor="middle"
                        dominantBaseline="central"
                        className="select-none pointer-events-none"
                        fill="#e2e8f0"
                        fontSize="11"
                        fontWeight={node.type === 'agent' ? '600' : '500'}
                        style={{ fontFamily: 'Inter, system-ui, sans-serif' }}
                      >
                        {labelText}
                      </text>
                    </>
                  );
                })()}

                {/* Risk indicator badge for agents with escalation risk */}
                {node.type === 'agent' && node.has_escalation_risk && (
                  <g transform={`translate(${radius - 6}, ${-radius + 6})`}>
                    <circle r="8" fill="#DC2626" stroke="#1a1a2e" strokeWidth="2" />
                    <text
                      textAnchor="middle"
                      y="4"
                      fill="white"
                      fontSize="10"
                      fontWeight="bold"
                      className="select-none"
                    >
                      !
                    </text>
                  </g>
                )}

                {/* Coverage gap indicator - amber warning badge (top-left) */}
                {node.hasCoverageGap && (
                  <g transform={`translate(${-radius + 6}, ${-radius + 6})`}>
                    <circle r="8" fill="#F59E0B" stroke="#1a1a2e" strokeWidth="2" />
                    <text
                      textAnchor="middle"
                      y="4"
                      fill="white"
                      fontSize="10"
                      fontWeight="bold"
                      className="select-none"
                    >
                      ?
                    </text>
                  </g>
                )}

                {/* Toxic combination indicator - pulsing red ring */}
                {node.isToxicCombination && (
                  <circle
                    r={radius + 5}
                    fill="none"
                    stroke="#DC2626"
                    strokeWidth="2"
                    strokeDasharray="3 2"
                    className="animate-pulse"
                    opacity="0.8"
                  />
                )}
              </g>
            );
          })}
        </g>
        </g>
      </svg>

      {/* Node details tooltip - styled like Knowledge Graph context menu */}
      {hoveredNode && (
        <div className="absolute top-4 left-4 bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-xl shadow-lg border border-surface-700/50 py-2 min-w-[200px] z-10">
          {(() => {
            const node = nodes.find((n) => n.id === hoveredNode);
            if (!node) return null;
            const color = getNodeColor(node);
            return (
              <>
                <div className="px-3 py-2 border-b border-surface-700/50">
                  <p className="text-sm font-semibold text-surface-100 truncate">
                    {node.label}
                  </p>
                  <p className="text-xs text-surface-400 capitalize flex items-center gap-1.5 mt-1">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                    {node.type}
                  </p>
                </div>

                <div className="px-3 py-2 space-y-1.5">
                  {node.classification && (
                    <div className="flex justify-between text-xs">
                      <span className="text-surface-400">Classification</span>
                      <span className="text-surface-200 capitalize font-medium">{node.classification}</span>
                    </div>
                  )}
                  {node.agent_type && (
                    <div className="flex justify-between text-xs">
                      <span className="text-surface-400">Agent Type</span>
                      <span className="text-surface-200 capitalize font-medium">{node.agent_type}</span>
                    </div>
                  )}
                  {node.capabilities_count !== undefined && (
                    <div className="flex justify-between text-xs">
                      <span className="text-surface-400">Capabilities</span>
                      <span className="text-surface-200 font-medium">{node.capabilities_count}</span>
                    </div>
                  )}
                  {node.has_escalation_risk && (
                    <div className="flex items-center gap-1.5 text-xs text-red-400 mt-2 pt-2 border-t border-surface-700/50">
                      <ShieldExclamationIcon className="h-4 w-4" />
                      <span className="font-medium">Escalation Risk Detected</span>
                    </div>
                  )}
                </div>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

export default CapabilityGraph;
