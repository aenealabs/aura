import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  MagnifyingGlassPlusIcon,
  MagnifyingGlassMinusIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  ArrowDownTrayIcon,
  ClipboardDocumentIcon,
  ExclamationTriangleIcon,
  XMarkIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';
import { Skeleton } from '../ui/LoadingSkeleton';
import { ConfidenceBadge } from './ConfidenceGauge';

// Export format configuration
const EXPORT_FORMATS = [
  { id: 'svg', label: 'SVG', description: 'Vector format, best for scaling' },
  { id: 'png', label: 'PNG', description: 'High-quality image with transparency' },
  { id: 'jpeg', label: 'JPEG', description: 'Compressed image format' },
  { id: 'pdf', label: 'PDF', description: 'Document format for reports' },
  { id: 'pptx', label: 'PowerPoint', description: 'Presentation slide format' },
];

// Background configuration for exports - macOS Tahoe dark theme
const EXPORT_BACKGROUND = {
  color: '#0a0a0f',
  gridColor: 'rgba(59, 130, 246, 0.08)',
  gridSize: 24,
};

/**
 * DiagramViewer Component
 *
 * Renders diagrams with zoom/pan controls.
 * ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.
 * ADR-060: Enterprise Diagram Generation with professional SVG support.
 *
 * Features:
 * - Mermaid.js rendering with dynamic import (CODE_ANALYSIS mode)
 * - Direct SVG rendering (AI_PROMPT mode with Eraser engine)
 * - Zoom in/out/reset controls
 * - Pan via mouse drag
 * - Copy code to clipboard
 * - SVG download
 * - Dark mode support
 * - Loading skeleton
 * - Error boundary
 */

// Mermaid configuration - macOS Tahoe inspired with Aura dark theme
// Design by Lucy - UI/UX Designer
const MERMAID_CONFIG = {
  startOnLoad: false,
  theme: 'base',
  themeCSS: `
    .actor-man circle { fill: #f97316 !important; }
    .sequenceNumber { fill: #000000 !important; font-weight: bold !important; }
    .messageLine0, .messageLine1 { stroke-width: 1px !important; }
    g.sequenceNumber rect { fill: #f97316 !important; }
    g.sequenceNumber text { fill: #000000 !important; font-weight: bold !important; }
    g rect.sequenceNumber { fill: #f97316 !important; }
    text.sequenceNumber { fill: #000000 !important; font-weight: bold !important; }
  `,
  themeVariables: {
    // Base colors - dark theme optimized
    primaryColor: '#1e3a5f',
    primaryTextColor: '#e0f2fe',
    primaryBorderColor: '#3b82f6',
    lineColor: '#4b5563',
    secondaryColor: '#1a2e35',
    tertiaryColor: '#0a0a0f',
    nodeTextColor: '#e0f2fe',
    background: 'transparent',
    mainBkg: 'transparent',
    nodeBkg: '#1e3a5f',
    nodeBorder: '#3b82f6',
    clusterBkg: 'rgba(59, 130, 246, 0.04)',
    clusterBorder: 'rgba(59, 130, 246, 0.15)',
    titleColor: '#e0f2fe',
    edgeLabelBackground: 'rgba(10, 10, 15, 0.9)',
    textColor: '#e0f2fe',
    labelTextColor: '#9ca3af',
    // Sequence diagram specific
    actorBkg: '#1e3a5f',
    actorBorder: '#3b82f6',
    actorTextColor: '#e0f2fe',
    actorLineColor: '#4b5563',
    signalColor: '#4b5563',
    signalTextColor: '#e0f2fe',
    labelBoxBkgColor: 'rgba(10, 10, 15, 0.9)',
    labelBoxBorderColor: '#3b82f6',
    // labelTextColor already defined above for sequence diagrams
    loopTextColor: '#9ca3af',
    noteBkgColor: '#1e3a5f',
    noteBorderColor: '#3b82f6',
    noteTextColor: '#e0f2fe',
    activationBkgColor: '#1e3a5f',
    activationBorderColor: '#3b82f6',
    sequenceNumberColor: '#000000',
  },
  flowchart: {
    htmlLabels: false, // Use SVG text elements for proper scaling
    curve: 'basis', // Smooth curved lines
    padding: 20,
    nodeSpacing: 60,
    rankSpacing: 70,
    useMaxWidth: false,
    defaultRenderer: 'dagre-wrapper',
  },
  sequence: {
    useMaxWidth: false,
    boxMargin: 10,
    boxTextMargin: 8,
    noteMargin: 12,
    messageMargin: 40,
    mirrorActors: false,
    bottomMarginAdj: 10,
    actorFontSize: 14,
    actorFontWeight: 500,
    noteFontSize: 13,
    messageFontSize: 13,
  },
  securityLevel: 'strict',
};

// Theme variables are consistent for all modes (dark-first design)
const DARK_THEME_VARIABLES = { ...MERMAID_CONFIG.themeVariables };

export function DiagramViewer({
  code = '',
  svgContent = '',  // ADR-060: Direct SVG content for professional diagrams
  dslContent = '',  // ADR-060: DSL source for professional diagrams
  renderEngine = 'mermaid',  // ADR-060: 'mermaid' or 'eraser'
  type = 'architecture',
  confidence = null,
  warnings = [],
  title = null,
  showControls = true,
  showConfidence = true,
  showWarnings = true,
  minZoom = 0.1,
  maxZoom = 10,
  initialZoom = 5.0, // Start at 500% for maximum visibility (10x original)
  loading = false,
  className = '',
}) {
  // ADR-060: Check if we have direct SVG content (professional diagrams)
  const hasDirectSvg = svgContent && svgContent.trim().length > 0;
  const isEraserEngine = renderEngine === 'eraser';
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const [mermaid, setMermaid] = useState(null);
  const [renderedSvg, setRenderedSvg] = useState('');
  const [renderError, setRenderError] = useState(null);
  const [zoom, setZoom] = useState(initialZoom);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [copied, setCopied] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const exportMenuRef = useRef(null);

  // Separate state for fullscreen view
  const [fullscreenZoom, setFullscreenZoom] = useState(10.0); // 1000% initial zoom
  const [fullscreenPosition, setFullscreenPosition] = useState({ x: 0, y: 0 });
  const [isFullscreenDragging, setIsFullscreenDragging] = useState(false);
  const [fullscreenDragStart, setFullscreenDragStart] = useState({ x: 0, y: 0 });

  // Detect dark mode
  useEffect(() => {
    const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
    setIsDarkMode(darkModeQuery.matches || document.documentElement.classList.contains('dark'));

    const handler = (e) => setIsDarkMode(e.matches);
    darkModeQuery.addEventListener('change', handler);
    return () => darkModeQuery.removeEventListener('change', handler);
  }, []);

  // Load Mermaid.js dynamically
  useEffect(() => {
    const loadMermaid = async () => {
      try {
        const mermaidModule = await import('mermaid');
        const mermaidInstance = mermaidModule.default;

        // Configure mermaid with theme
        const themeVariables = isDarkMode
          ? { ...MERMAID_CONFIG.themeVariables, ...DARK_THEME_VARIABLES }
          : MERMAID_CONFIG.themeVariables;

        mermaidInstance.initialize({
          ...MERMAID_CONFIG,
          theme: isDarkMode ? 'dark' : 'base',
          themeVariables,
        });

        setMermaid(mermaidInstance);
      } catch (err) {
        console.error('Failed to load Mermaid:', err);
        setRenderError(new Error('Failed to load diagram renderer'));
      }
    };

    loadMermaid();
  }, [isDarkMode]);

  // ADR-060: Handle direct SVG content for professional diagrams
  useEffect(() => {
    if (hasDirectSvg) {
      setRenderedSvg(svgContent);
      setRenderError(null);
    }
  }, [hasDirectSvg, svgContent]);

  // Render Mermaid diagram when code or mermaid instance changes (only if no direct SVG)
  useEffect(() => {
    // Skip Mermaid rendering if we have direct SVG content
    if (hasDirectSvg) {
      return;
    }

    if (!mermaid || !code) {
      setRenderedSvg('');
      setRenderError(null);
      return;
    }

    const renderDiagram = async () => {
      try {
        setRenderError(null);

        // Generate unique ID for this render
        const id = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

        // Render the diagram
        const { svg } = await mermaid.render(id, code);

        // Skip post-processing for sequence diagrams - use Mermaid's native output
        const isSequenceDiagram = code.trim().toLowerCase().startsWith('sequencediagram');
        if (isSequenceDiagram) {
          setRenderedSvg(svg);
        } else {
          // Post-process SVG to ensure proper scaling for other diagram types
          const processedSvg = postProcessSvg(svg);
          setRenderedSvg(processedSvg);
        }
      } catch (err) {
        console.error('Mermaid render error:', err);
        setRenderError(err);
        setRenderedSvg('');
      }
    };

    renderDiagram();
  }, [mermaid, code, hasDirectSvg]);

  // Post-process SVG for responsive scaling only (no stroke manipulation)
  const postProcessSvg = (svgString) => {
    const parser = new DOMParser();
    const doc = parser.parseFromString(svgString, 'image/svg+xml');
    const svg = doc.querySelector('svg');

    if (!svg) return svgString;

    // Ensure viewBox is set for proper scaling
    if (!svg.getAttribute('viewBox')) {
      const width = parseFloat(svg.getAttribute('width')) || 800;
      const height = parseFloat(svg.getAttribute('height')) || 600;
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    }

    // Set preserveAspectRatio to ensure content scales uniformly
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    // Remove fixed width/height to allow responsive scaling
    svg.removeAttribute('width');
    svg.removeAttribute('height');
    svg.style.width = '100%';
    svg.style.height = '100%';
    svg.style.maxWidth = '100%';

    const serializer = new XMLSerializer();
    return serializer.serializeToString(doc);
  };

  // Zoom controls
  const handleZoomIn = useCallback(() => {
    setZoom((prev) => Math.min(prev * 1.25, maxZoom));
  }, [maxZoom]);

  const handleZoomOut = useCallback(() => {
    setZoom((prev) => Math.max(prev / 1.25, minZoom));
  }, [minZoom]);

  const handleZoomReset = useCallback(() => {
    setZoom(initialZoom);
    setPosition({ x: 0, y: 0 });
  }, [initialZoom]);

  // Fullscreen modal handlers
  const handleOpenFullscreen = useCallback(() => {
    setIsFullscreen(true);
    setFullscreenZoom(10.0); // 1000% zoom
    setFullscreenPosition({ x: 0, y: 0 });
  }, []);

  const handleCloseFullscreen = useCallback(() => {
    setIsFullscreen(false);
  }, []);

  // Fullscreen zoom controls
  const handleFullscreenZoomIn = useCallback(() => {
    setFullscreenZoom((prev) => Math.min(prev * 1.25, maxZoom));
  }, [maxZoom]);

  const handleFullscreenZoomOut = useCallback(() => {
    setFullscreenZoom((prev) => Math.max(prev / 1.25, minZoom));
  }, [minZoom]);

  const handleFullscreenZoomReset = useCallback(() => {
    setFullscreenZoom(10.0); // Reset to 1000%
    setFullscreenPosition({ x: 0, y: 0 });
  }, []);

  // Fullscreen mouse wheel zoom
  const handleFullscreenWheel = useCallback(
    (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      setFullscreenZoom((prev) => Math.max(minZoom, Math.min(maxZoom, prev * delta)));
    },
    [minZoom, maxZoom]
  );

  // Fullscreen pan controls
  const handleFullscreenMouseDown = useCallback((e) => {
    if (e.button === 0) {
      setIsFullscreenDragging(true);
      setFullscreenDragStart({ x: e.clientX - fullscreenPosition.x, y: e.clientY - fullscreenPosition.y });
    }
  }, [fullscreenPosition]);

  const handleFullscreenMouseMove = useCallback(
    (e) => {
      if (isFullscreenDragging) {
        setFullscreenPosition({
          x: e.clientX - fullscreenDragStart.x,
          y: e.clientY - fullscreenDragStart.y,
        });
      }
    },
    [isFullscreenDragging, fullscreenDragStart]
  );

  const handleFullscreenMouseUp = useCallback(() => {
    setIsFullscreenDragging(false);
  }, []);

  // Close fullscreen on Escape key
  useEffect(() => {
    if (!isFullscreen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        handleCloseFullscreen();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen, handleCloseFullscreen]);

  // Mouse wheel zoom
  const handleWheel = useCallback(
    (e) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        setZoom((prev) => Math.max(minZoom, Math.min(maxZoom, prev * delta)));
      }
    },
    [minZoom, maxZoom]
  );

  // Pan controls
  const handleMouseDown = useCallback((e) => {
    if (e.button === 0) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  }, [position]);

  const handleMouseMove = useCallback(
    (e) => {
      if (isDragging) {
        setPosition({
          x: e.clientX - dragStart.x,
          y: e.clientY - dragStart.y,
        });
      }
    },
    [isDragging, dragStart]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Close export menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target)) {
        setShowExportMenu(false);
      }
    };
    if (showExportMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showExportMenu]);

  // Copy code to clipboard - ADR-060: Copy DSL for eraser, Mermaid for mermaid
  const handleCopy = useCallback(async () => {
    try {
      const contentToCopy = isEraserEngine ? dslContent : code;
      await navigator.clipboard.writeText(contentToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, [code, dslContent, isEraserEngine]);

  // Create SVG with embedded dark background and grid pattern
  const createExportSvg = useCallback(() => {
    if (!renderedSvg) return null;

    const parser = new DOMParser();
    const doc = parser.parseFromString(renderedSvg, 'image/svg+xml');
    const svg = doc.querySelector('svg');

    if (!svg) return null;

    // Ensure proper XML namespace
    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    svg.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

    // Convert foreignObject HTML content to text for better canvas compatibility
    const foreignObjects = svg.querySelectorAll('foreignObject');
    foreignObjects.forEach(fo => {
      const div = fo.querySelector('div');
      if (div) {
        const text = div.textContent || '';
        const parent = fo.parentNode;
        const x = fo.getAttribute('x') || '0';
        const y = fo.getAttribute('y') || '0';
        const textNode = doc.createElementNS('http://www.w3.org/2000/svg', 'text');
        textNode.setAttribute('x', x);
        textNode.setAttribute('y', parseFloat(y) + 14); // Adjust for baseline
        textNode.setAttribute('fill', '#e0f2fe');
        textNode.setAttribute('font-family', 'Inter, system-ui, sans-serif');
        textNode.setAttribute('font-size', '14');
        textNode.textContent = text;
        parent.replaceChild(textNode, fo);
      }
    });

    // Get dimensions from SVG attributes or viewBox
    let width = parseFloat(svg.getAttribute('width')) || 800;
    let height = parseFloat(svg.getAttribute('height')) || 600;
    let viewBoxX = 0, viewBoxY = 0;

    // Parse viewBox if present
    const viewBox = svg.getAttribute('viewBox');
    if (viewBox) {
      const parts = viewBox.split(/\s+|,/).map(parseFloat);
      if (parts.length === 4) {
        viewBoxX = parts[0];
        viewBoxY = parts[1];
        width = parts[2] || width;
        height = parts[3] || height;
      }
    }

    // Add padding
    const padding = 60;
    viewBoxX -= padding;
    viewBoxY -= padding;
    width += padding * 2;
    height += padding * 2;

    // Set SVG dimensions
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', `${viewBoxX} ${viewBoxY} ${width} ${height}`);
    svg.removeAttribute('style');

    // Create defs for grid pattern
    let defs = svg.querySelector('defs');
    if (!defs) {
      defs = doc.createElementNS('http://www.w3.org/2000/svg', 'defs');
      svg.insertBefore(defs, svg.firstChild);
    }

    // Add grid pattern definition
    const patternId = `export-grid-${Date.now()}`;
    const pattern = doc.createElementNS('http://www.w3.org/2000/svg', 'pattern');
    pattern.setAttribute('id', patternId);
    pattern.setAttribute('width', EXPORT_BACKGROUND.gridSize);
    pattern.setAttribute('height', EXPORT_BACKGROUND.gridSize);
    pattern.setAttribute('patternUnits', 'userSpaceOnUse');

    // Horizontal grid line
    const hLine = doc.createElementNS('http://www.w3.org/2000/svg', 'line');
    hLine.setAttribute('x1', '0');
    hLine.setAttribute('y1', '0');
    hLine.setAttribute('x2', EXPORT_BACKGROUND.gridSize);
    hLine.setAttribute('y2', '0');
    hLine.setAttribute('stroke', EXPORT_BACKGROUND.gridColor);
    hLine.setAttribute('stroke-width', '1');
    pattern.appendChild(hLine);

    // Vertical grid line
    const vLine = doc.createElementNS('http://www.w3.org/2000/svg', 'line');
    vLine.setAttribute('x1', '0');
    vLine.setAttribute('y1', '0');
    vLine.setAttribute('x2', '0');
    vLine.setAttribute('y2', EXPORT_BACKGROUND.gridSize);
    vLine.setAttribute('stroke', EXPORT_BACKGROUND.gridColor);
    vLine.setAttribute('stroke-width', '1');
    pattern.appendChild(vLine);

    defs.appendChild(pattern);

    // Create background rect with solid color
    const bgRect = doc.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bgRect.setAttribute('x', viewBoxX);
    bgRect.setAttribute('y', viewBoxY);
    bgRect.setAttribute('width', width);
    bgRect.setAttribute('height', height);
    bgRect.setAttribute('fill', EXPORT_BACKGROUND.color);
    svg.insertBefore(bgRect, defs.nextSibling);

    // Create grid overlay rect
    const gridRect = doc.createElementNS('http://www.w3.org/2000/svg', 'rect');
    gridRect.setAttribute('x', viewBoxX);
    gridRect.setAttribute('y', viewBoxY);
    gridRect.setAttribute('width', width);
    gridRect.setAttribute('height', height);
    gridRect.setAttribute('fill', `url(#${patternId})`);
    svg.insertBefore(gridRect, bgRect.nextSibling);

    // Remove any white background rects from the original content
    const whiteRects = svg.querySelectorAll('rect[fill="#ffffff"], rect[fill="white"], rect[fill="#fff"], rect[fill="rgb(255, 255, 255)"]');
    whiteRects.forEach(rect => {
      const rectWidth = parseFloat(rect.getAttribute('width') || 0);
      const rectHeight = parseFloat(rect.getAttribute('height') || 0);
      if (rectWidth > width * 0.8 && rectHeight > height * 0.8) {
        rect.remove();
      }
    });

    const serializer = new XMLSerializer();
    return {
      svgString: serializer.serializeToString(doc),
      width,
      height,
    };
  }, [renderedSvg]);

  // Export as SVG
  const exportSvg = useCallback(() => {
    const result = createExportSvg();
    if (!result) return;

    const blob = new Blob([result.svgString], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${type}-diagram.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [createExportSvg, type]);

  // Convert SVG to canvas for raster exports
  const svgToCanvas = useCallback((svgString, width, height) => {
    return new Promise((resolve, reject) => {
      const canvas = document.createElement('canvas');
      const scale = 2; // 2x resolution for crisp exports
      canvas.width = width * scale;
      canvas.height = height * scale;
      const ctx = canvas.getContext('2d');
      ctx.scale(scale, scale);

      // Fill with dark background first (in case SVG has transparency issues)
      ctx.fillStyle = EXPORT_BACKGROUND.color;
      ctx.fillRect(0, 0, width, height);

      const img = new Image();

      // Use data URL instead of blob URL for better compatibility
      // Also encode the SVG properly to handle special characters
      const encodedSvg = encodeURIComponent(svgString)
        .replace(/'/g, '%27')
        .replace(/"/g, '%22');
      const dataUrl = `data:image/svg+xml;charset=utf-8,${encodedSvg}`;

      img.onload = () => {
        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas);
      };

      img.onerror = (err) => {
        console.error('Image load failed, trying alternative method:', err);
        // Fallback: try with blob URL
        const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
        const blobUrl = URL.createObjectURL(svgBlob);
        const fallbackImg = new Image();

        fallbackImg.onload = () => {
          ctx.drawImage(fallbackImg, 0, 0, width, height);
          URL.revokeObjectURL(blobUrl);
          resolve(canvas);
        };

        fallbackImg.onerror = (fallbackErr) => {
          URL.revokeObjectURL(blobUrl);
          reject(fallbackErr);
        };

        fallbackImg.src = blobUrl;
      };

      img.src = dataUrl;
    });
  }, []);

  // Export as PNG
  const exportPng = useCallback(async () => {
    const result = createExportSvg();
    if (!result) return;

    try {
      const canvas = await svgToCanvas(result.svgString, result.width, result.height);
      const dataUrl = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = `${type}-diagram.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error('PNG export failed:', err);
    }
  }, [createExportSvg, svgToCanvas, type]);

  // Export as JPEG
  const exportJpeg = useCallback(async () => {
    const result = createExportSvg();
    if (!result) return;

    try {
      const canvas = await svgToCanvas(result.svgString, result.width, result.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = `${type}-diagram.jpg`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error('JPEG export failed:', err);
    }
  }, [createExportSvg, svgToCanvas, type]);

  // Export as PDF
  const exportPdf = useCallback(async () => {
    const result = createExportSvg();
    if (!result) return;

    try {
      const { jsPDF } = await import('jspdf');
      const canvas = await svgToCanvas(result.svgString, result.width, result.height);

      // Determine orientation based on dimensions
      const isLandscape = result.width > result.height;
      const pdf = new jsPDF({
        orientation: isLandscape ? 'landscape' : 'portrait',
        unit: 'px',
        format: [result.width + 40, result.height + 80],
      });

      // Add dark background to PDF
      pdf.setFillColor(10, 10, 15);
      pdf.rect(0, 0, result.width + 40, result.height + 80, 'F');

      // Add title
      pdf.setTextColor(224, 242, 254);
      pdf.setFontSize(16);
      const titleText = `${type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')} Diagram`;
      pdf.text(titleText, 20, 30);

      // Add diagram image
      const imgData = canvas.toDataURL('image/png');
      pdf.addImage(imgData, 'PNG', 20, 50, result.width, result.height);

      // Add footer
      pdf.setFontSize(10);
      pdf.setTextColor(156, 163, 175);
      pdf.text('Generated by Project Aura Documentation Generator', 20, result.height + 70);

      pdf.save(`${type}-diagram.pdf`);
    } catch (err) {
      console.error('PDF export failed:', err);
    }
  }, [createExportSvg, svgToCanvas, type]);

  // Export as PowerPoint
  const exportPptx = useCallback(async () => {
    const result = createExportSvg();
    if (!result) return;

    try {
      const pptxgenjs = await import('pptxgenjs');
      const PptxGenJS = pptxgenjs.default;
      const pptx = new PptxGenJS();

      // Set presentation properties
      pptx.author = 'Project Aura';
      pptx.title = `${type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')} Diagram`;
      pptx.subject = 'Architecture Documentation';

      // Create slide with dark background
      const slide = pptx.addSlide();
      slide.background = { color: '0a0a0f' };

      // Add title
      const titleText = `${type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')} Diagram`;
      slide.addText(titleText, {
        x: 0.5,
        y: 0.3,
        w: '90%',
        h: 0.5,
        fontSize: 24,
        fontFace: 'Arial',
        color: 'e0f2fe',
        bold: true,
      });

      // Convert SVG to image for PPT
      const canvas = await svgToCanvas(result.svgString, result.width, result.height);
      const imgData = canvas.toDataURL('image/png');

      // Calculate dimensions to fit slide (10" x 7.5" default)
      const slideWidth = 10;
      const slideHeight = 7.5;
      const maxWidth = slideWidth - 1;
      const maxHeight = slideHeight - 1.5;

      const aspectRatio = result.width / result.height;
      let imgWidth = maxWidth;
      let imgHeight = imgWidth / aspectRatio;

      if (imgHeight > maxHeight) {
        imgHeight = maxHeight;
        imgWidth = imgHeight * aspectRatio;
      }

      // Center the image
      const xPos = (slideWidth - imgWidth) / 2;
      const yPos = 1 + (maxHeight - imgHeight) / 2;

      slide.addImage({
        data: imgData,
        x: xPos,
        y: yPos,
        w: imgWidth,
        h: imgHeight,
      });

      // Add footer
      slide.addText('Generated by Project Aura Documentation Generator', {
        x: 0.5,
        y: slideHeight - 0.5,
        w: '90%',
        h: 0.3,
        fontSize: 10,
        fontFace: 'Arial',
        color: '9ca3af',
      });

      await pptx.writeFile({ fileName: `${type}-diagram.pptx` });
    } catch (err) {
      console.error('PowerPoint export failed:', err);
    }
  }, [createExportSvg, svgToCanvas, type]);

  // Handle export based on format
  const handleExport = useCallback(async (format) => {
    setIsExporting(true);
    setShowExportMenu(false);

    try {
      switch (format) {
        case 'svg':
          exportSvg();
          break;
        case 'png':
          await exportPng();
          break;
        case 'jpeg':
          await exportJpeg();
          break;
        case 'pdf':
          await exportPdf();
          break;
        case 'pptx':
          await exportPptx();
          break;
        default:
          exportSvg();
      }
    } catch (err) {
      console.error(`Export failed for format ${format}:`, err);
    } finally {
      setIsExporting(false);
    }
  }, [exportSvg, exportPng, exportJpeg, exportPdf, exportPptx]);

  // Legacy download handler (defaults to SVG)
  const handleDownload = useCallback(() => {
    exportSvg();
  }, [exportSvg]);

  // Format diagram type for display
  const formatType = (t) => {
    return t
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  if (loading) {
    return (
      <div className={`bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 ${className}`}>
        <div className="p-4 border-b border-surface-200 dark:border-surface-700">
          <Skeleton className="w-40 h-6 rounded" />
        </div>
        <div className="p-8">
          <Skeleton className="w-full h-64 rounded-lg" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={`bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">
            {title || `${formatType(type)} Diagram`}
          </h3>
          {showConfidence && confidence !== null && (
            <ConfidenceBadge score={confidence} size="sm" />
          )}
        </div>

        {/* Controls */}
        {showControls && (
          <div className="flex items-center gap-1">
            <button
              onClick={handleZoomOut}
              className="p-1.5 rounded-md text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700 transition-colors"
              title="Zoom out"
              aria-label="Zoom out"
            >
              <MagnifyingGlassMinusIcon className="w-5 h-5" />
            </button>
            <span className="px-2 text-sm text-surface-600 dark:text-surface-400 min-w-[3rem] text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={handleZoomIn}
              className="p-1.5 rounded-md text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700 transition-colors"
              title="Zoom in"
              aria-label="Zoom in"
            >
              <MagnifyingGlassPlusIcon className="w-5 h-5" />
            </button>
            <button
              onClick={handleOpenFullscreen}
              className="p-1.5 rounded-md text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700 transition-colors"
              title="Expand to fullscreen"
              aria-label="Expand to fullscreen"
            >
              <ArrowsPointingOutIcon className="w-5 h-5" />
            </button>
            <div className="w-px h-5 bg-surface-200 dark:bg-surface-700 mx-1" />
            <button
              onClick={handleCopy}
              className={`p-1.5 rounded-md transition-colors ${
                copied
                  ? 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/30'
                  : 'text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700'
              }`}
              title={copied ? 'Copied!' : 'Copy code'}
              aria-label={copied ? 'Copied!' : 'Copy code'}
            >
              <ClipboardDocumentIcon className="w-5 h-5" />
            </button>
            {/* Export Dropdown */}
            <div className="relative" ref={exportMenuRef}>
              <button
                onClick={() => setShowExportMenu(!showExportMenu)}
                disabled={!renderedSvg || isExporting}
                className="flex items-center gap-1 px-2 py-1.5 rounded-md text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="Export diagram"
                aria-label="Export diagram"
                aria-haspopup="true"
                aria-expanded={showExportMenu}
              >
                {isExporting ? (
                  <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <ArrowDownTrayIcon className="w-5 h-5" />
                )}
                <ChevronDownIcon className="w-3 h-3" />
              </button>
              {showExportMenu && (
                <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-surface-800 rounded-lg shadow-lg border border-surface-200 dark:border-surface-700 py-1 z-50">
                  {EXPORT_FORMATS.map((format) => (
                    <button
                      key={format.id}
                      onClick={() => handleExport(format.id)}
                      className="w-full px-3 py-2 text-left hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
                    >
                      <div className="text-sm font-medium text-surface-900 dark:text-surface-100">
                        {format.label}
                      </div>
                      <div className="text-xs text-surface-500 dark:text-surface-400">
                        {format.description}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Warnings */}
      {showWarnings && warnings.length > 0 && (
        <div className="px-4 py-2 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800">
          <div className="flex items-start gap-2">
            <ExclamationTriangleIcon className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-amber-700 dark:text-amber-300">
              {warnings.map((warning, i) => (
                <p key={i}>{warning}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Diagram Container - Fixed height card with overflow hidden */}
      <div
        ref={containerRef}
        className={`relative overflow-hidden rounded-lg ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
        style={{
          height: 600, // Fixed card height for larger diagram visibility
          backgroundColor: '#0a0a0f',
          backgroundImage: `
            linear-gradient(rgba(59, 130, 246, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(59, 130, 246, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: '24px 24px',
          boxShadow: 'inset 0 0 120px rgba(59, 130, 246, 0.04), inset 0 1px 0 rgba(255, 255, 255, 0.02)',
        }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        role="img"
        aria-label={`${formatType(type)} diagram`}
      >
        {renderError ? (
          <div className="flex flex-col items-center justify-center h-64 text-center px-4">
            <ExclamationTriangleIcon className="w-12 h-12 text-amber-500 mb-3" />
            <p className="text-surface-700 dark:text-surface-300 font-medium">
              Failed to render diagram
            </p>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
              {renderError.message || 'Invalid Mermaid syntax'}
            </p>
            <pre className="mt-4 p-3 bg-surface-100 dark:bg-surface-900 rounded-lg text-xs text-left max-w-full overflow-auto max-h-32">
              {code}
            </pre>
          </div>
        ) : !renderedSvg ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-pulse text-surface-400">Loading diagram...</div>
          </div>
        ) : (
          <>
            <div
              ref={svgRef}
              className="diagram-svg-container flex items-center justify-center p-4 h-full transition-transform duration-100"
              style={{
                transform: `translate(${position.x}px, ${position.y}px) scale(${zoom})`,
                transformOrigin: 'center center',
              }}
            >
              <style>{`
                .diagram-svg-container svg {
                  overflow: visible;
                  max-width: none;
                  max-height: 280px;
                }
                .diagram-svg-container svg text {
                  font-family: Inter, system-ui, -apple-system, sans-serif;
                }
                .diagram-svg-container svg .node rect,
                .diagram-svg-container svg .node circle,
                .diagram-svg-container svg .node ellipse,
                .diagram-svg-container svg .node polygon,
                .diagram-svg-container svg .node path {
                  vector-effect: non-scaling-stroke;
                }
                .diagram-svg-container svg[aria-roledescription="sequence"] circle {
                  fill: #f97316 !important;
                }
                .diagram-svg-container svg[aria-roledescription="sequence"] text.sequenceNumber {
                  fill: #000000 !important;
                  font-weight: 700 !important;
                }
              `}</style>
              <div dangerouslySetInnerHTML={{ __html: renderedSvg }} />
            </div>
            {/* Fade hint at bottom */}
            <div
              className="absolute bottom-0 left-0 right-0 h-12 pointer-events-none"
              style={{
                background: 'linear-gradient(to top, rgba(10, 10, 15, 0.95), transparent)',
              }}
            />
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 text-xs text-surface-500 flex items-center gap-1.5 pointer-events-none">
              <ArrowsPointingOutIcon className="w-3.5 h-3.5" />
              <span>Expand for full view</span>
            </div>
          </>
        )}
      </div>

      {/* Code preview toggle (optional) - ADR-060: Show DSL for eraser, Mermaid for mermaid */}
      {(code || dslContent) && (
        <details className="border-t border-surface-200 dark:border-surface-700">
          <summary className="px-4 py-2 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700/50 cursor-pointer select-none">
            {isEraserEngine ? 'View Diagram DSL' : 'View Mermaid Code'}
          </summary>
          <pre className="p-4 bg-surface-50 dark:bg-surface-900 text-xs overflow-x-auto font-mono text-surface-700 dark:text-surface-300">
            {isEraserEngine ? dslContent : code}
          </pre>
        </details>
      )}

      {/* Fullscreen Modal */}
      {isFullscreen &&
        createPortal(
          <div
            className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center"
            onClick={handleCloseFullscreen}
            role="dialog"
            aria-modal="true"
            aria-label={`${formatType(type)} diagram fullscreen view`}
          >
            {/* Modal Content */}
            <div
              className="relative w-[90vw] h-[90vh] bg-white dark:bg-surface-800 rounded-xl shadow-2xl overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-900">
                <div className="flex items-center gap-3">
                  <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                    {title || `${formatType(type)} Diagram`}
                  </h3>
                  {showConfidence && confidence !== null && (
                    <ConfidenceBadge score={confidence} size="sm" />
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {/* Zoom Controls */}
                  <button
                    onClick={handleFullscreenZoomOut}
                    className="p-2 rounded-lg text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700 transition-colors"
                    title="Zoom out"
                    aria-label="Zoom out"
                  >
                    <MagnifyingGlassMinusIcon className="w-5 h-5" />
                  </button>
                  <span className="px-2 text-sm text-surface-600 dark:text-surface-400 min-w-[3.5rem] text-center font-medium">
                    {Math.round(fullscreenZoom * 100)}%
                  </span>
                  <button
                    onClick={handleFullscreenZoomIn}
                    className="p-2 rounded-lg text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700 transition-colors"
                    title="Zoom in"
                    aria-label="Zoom in"
                  >
                    <MagnifyingGlassPlusIcon className="w-5 h-5" />
                  </button>
                  <button
                    onClick={handleFullscreenZoomReset}
                    className="p-2 rounded-lg text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700 transition-colors"
                    title="Reset view"
                    aria-label="Reset view"
                  >
                    <ArrowsPointingInIcon className="w-5 h-5" />
                  </button>
                  <div className="w-px h-6 bg-surface-300 dark:bg-surface-600 mx-1" />
                  <button
                    onClick={handleCopy}
                    className={`p-2 rounded-lg transition-colors ${
                      copied
                        ? 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/30'
                        : 'text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700'
                    }`}
                    title={copied ? 'Copied!' : 'Copy code'}
                    aria-label={copied ? 'Copied!' : 'Copy code'}
                  >
                    <ClipboardDocumentIcon className="w-5 h-5" />
                  </button>
                  {/* Export Dropdown in Fullscreen */}
                  <div className="relative">
                    <button
                      onClick={() => setShowExportMenu(!showExportMenu)}
                      disabled={!renderedSvg || isExporting}
                      className="flex items-center gap-1 px-3 py-2 rounded-lg text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700 transition-colors disabled:opacity-50"
                      title="Export diagram"
                      aria-label="Export diagram"
                      aria-haspopup="true"
                      aria-expanded={showExportMenu}
                    >
                      {isExporting ? (
                        <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      ) : (
                        <ArrowDownTrayIcon className="w-5 h-5" />
                      )}
                      <ChevronDownIcon className="w-3 h-3" />
                    </button>
                    {showExportMenu && (
                      <div className="absolute right-0 mt-1 w-52 bg-white dark:bg-surface-800 rounded-lg shadow-xl border border-surface-200 dark:border-surface-700 py-1 z-[110]">
                        {EXPORT_FORMATS.map((format) => (
                          <button
                            key={format.id}
                            onClick={() => handleExport(format.id)}
                            className="w-full px-4 py-2.5 text-left hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
                          >
                            <div className="text-sm font-medium text-surface-900 dark:text-surface-100">
                              {format.label}
                            </div>
                            <div className="text-xs text-surface-500 dark:text-surface-400">
                              {format.description}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={handleCloseFullscreen}
                    className="p-2 rounded-lg text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-700 transition-colors"
                    title="Close (Esc)"
                    aria-label="Close fullscreen"
                  >
                    <XMarkIcon className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Modal Body - Interactive Diagram with grid background */}
              <div
                className={`h-[calc(90vh-4rem)] overflow-hidden ${isFullscreenDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
                style={{
                  backgroundColor: '#0a0a0f',
                  backgroundImage: `
                    linear-gradient(rgba(59, 130, 246, 0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(59, 130, 246, 0.03) 1px, transparent 1px)
                  `,
                  backgroundSize: '24px 24px',
                  boxShadow: 'inset 0 0 200px rgba(59, 130, 246, 0.04)',
                }}
                onWheel={handleFullscreenWheel}
                onMouseDown={handleFullscreenMouseDown}
                onMouseMove={handleFullscreenMouseMove}
                onMouseUp={handleFullscreenMouseUp}
                onMouseLeave={handleFullscreenMouseUp}
              >
                {renderError ? (
                  <div className="flex flex-col items-center justify-center h-full text-center">
                    <ExclamationTriangleIcon className="w-16 h-16 text-amber-500 mb-4" />
                    <p className="text-surface-700 dark:text-surface-300 font-medium text-lg">
                      Failed to render diagram
                    </p>
                    <p className="text-surface-500 dark:text-surface-400 mt-2">
                      {renderError.message || 'Invalid Mermaid syntax'}
                    </p>
                  </div>
                ) : renderedSvg ? (
                  <div
                    className="diagram-svg-container w-full h-full flex items-center justify-center"
                    style={{
                      transform: `translate(${fullscreenPosition.x}px, ${fullscreenPosition.y}px) scale(${fullscreenZoom})`,
                      transformOrigin: 'center center',
                      transition: isFullscreenDragging ? 'none' : 'transform 0.1s ease-out',
                    }}
                  >
                    <style>{`
                      .diagram-svg-container svg {
                        overflow: visible;
                        max-width: none;
                      }
                      .diagram-svg-container svg text {
                        font-family: Inter, system-ui, -apple-system, sans-serif;
                      }
                      .diagram-svg-container svg .node rect,
                      .diagram-svg-container svg .node circle,
                      .diagram-svg-container svg .node ellipse,
                      .diagram-svg-container svg .node polygon,
                      .diagram-svg-container svg .node path {
                        vector-effect: non-scaling-stroke;
                      }
                      .diagram-svg-container svg[aria-roledescription="sequence"] circle {
                        fill: #f97316 !important;
                      }
                      .diagram-svg-container svg[aria-roledescription="sequence"] text.sequenceNumber {
                        fill: #000000 !important;
                        font-weight: 700 !important;
                      }
                    `}</style>
                    <div dangerouslySetInnerHTML={{ __html: renderedSvg }} />
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <div className="animate-pulse text-surface-400 text-lg">Loading diagram...</div>
                  </div>
                )}
              </div>

              {/* Modal Footer - Keyboard Hint */}
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-sm text-surface-400 dark:text-surface-500 bg-surface-100/80 dark:bg-surface-800/80 px-3 py-1.5 rounded-full backdrop-blur-sm">
                Scroll to zoom • Drag to pan • <kbd className="px-1.5 py-0.5 bg-surface-200 dark:bg-surface-700 rounded text-xs font-mono">Esc</kbd> to close
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}

/**
 * DiagramGrid
 *
 * Grid layout for multiple diagrams.
 * ADR-060: Supports both Mermaid and professional SVG diagrams.
 */
export function DiagramGrid({ diagrams = [], columns = 2, className = '' }) {
  if (!diagrams.length) {
    return (
      <div className="text-center py-12 text-surface-500 dark:text-surface-400">
        No diagrams available
      </div>
    );
  }

  return (
    <div
      className={`grid gap-4 ${className}`}
      style={{
        gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
      }}
    >
      {diagrams.map((diagram, index) => (
        <DiagramViewer
          key={diagram.diagramType || index}
          code={diagram.mermaidCode}
          svgContent={diagram.svgContent}
          dslContent={diagram.dslContent}
          renderEngine={diagram.renderEngine}
          type={diagram.diagramType}
          confidence={diagram.confidence}
          warnings={diagram.warnings}
        />
      ))}
    </div>
  );
}

export default DiagramViewer;
