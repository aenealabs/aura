import { useState, useEffect, useCallback } from 'react';
import {
  ArrowPathIcon,
  DocumentTextIcon,
  RectangleStackIcon,
  CubeTransparentIcon,
  PlayIcon,
  StopIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ChartBarIcon,
  ArrowDownTrayIcon,
  HandThumbUpIcon,
  HandThumbDownIcon,
  DocumentDuplicateIcon,
  ServerStackIcon,
  CircleStackIcon,
  ArrowsRightLeftIcon,
  ChevronRightIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { jsPDF } from 'jspdf';
import { useToast } from '../ui/Toast';
import { Skeleton } from '../ui/LoadingSkeleton';
import { useDocumentationData } from '../../hooks/useDocumentationData';
import { ConfidenceGauge, ConfidenceBadge, ConfidenceBar } from './ConfidenceGauge';
import { DiagramViewer, DiagramGrid } from './DiagramViewer';
import { MOCK_REPOSITORIES } from '../../services/documentationApi';

/**
 * DocumentationDashboard Component
 *
 * Main dashboard for generating and viewing architecture documentation.
 * ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.
 *
 * Features:
 * - Repository selection
 * - Diagram type selection
 * - Real-time streaming progress
 * - Tab navigation: Diagrams | Report | Service Boundaries
 * - Feedback submission for confidence calibration
 */

// Diagram type metadata
const DIAGRAM_TYPE_INFO = {
  architecture: {
    label: 'Architecture',
    description: 'High-level service architecture and component relationships',
    icon: CubeTransparentIcon,
  },
  data_flow: {
    label: 'Data Flow',
    description: 'Data movement between services, databases, and external systems',
    icon: ArrowsRightLeftIcon,
  },
  dependency: {
    label: 'Dependencies',
    description: 'Module and package dependency graph',
    icon: RectangleStackIcon,
  },
  sequence: {
    label: 'Sequence',
    description: 'Request/response flow for key operations',
    icon: ChevronRightIcon,
  },
  component: {
    label: 'Component',
    description: 'Internal component structure within services',
    icon: DocumentDuplicateIcon,
  },
};

// Progress phase metadata
const PHASE_INFO = {
  idle: { label: 'Ready', color: 'surface' },
  starting: { label: 'Starting', color: 'aura' },
  analyzing: { label: 'Analyzing Code', color: 'aura' },
  detecting_boundaries: { label: 'Detecting Services', color: 'aura' },
  generating_diagrams: { label: 'Generating Diagrams', color: 'aura' },
  generating_report: { label: 'Generating Report', color: 'aura' },
  complete: { label: 'Complete', color: 'olive' },
  error: { label: 'Error', color: 'critical' },
  cancelled: { label: 'Cancelled', color: 'warning' },
};


/**
 * Progress indicator during generation
 */
function GenerationProgress({ progress, onCancel }) {
  const phaseInfo = PHASE_INFO[progress.phase] || PHASE_INFO.idle;
  const isActive = !['idle', 'complete', 'error', 'cancelled'].includes(progress.phase);

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {isActive && (
            <div className="animate-spin">
              <ArrowPathIcon className="w-5 h-5 text-aura-500" />
            </div>
          )}
          {progress.phase === 'complete' && (
            <CheckCircleIcon className="w-5 h-5 text-olive-500" />
          )}
          {progress.phase === 'error' && (
            <ExclamationTriangleIcon className="w-5 h-5 text-critical-500" />
          )}
          <span className="font-medium text-surface-900 dark:text-surface-100">
            {phaseInfo.label}
          </span>
        </div>

        {isActive && onCancel && (
          <button
            onClick={onCancel}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-critical-600 hover:text-critical-700 dark:text-critical-400 dark:hover:text-critical-300 transition-colors"
          >
            <StopIcon className="w-4 h-4" />
            Cancel
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-3">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-surface-600 dark:text-surface-400">{progress.message}</span>
          <span className="text-surface-500 dark:text-surface-500">{progress.progress}%</span>
        </div>
        <div className="w-full h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ease-out ${
              progress.phase === 'error'
                ? 'bg-critical-500'
                : progress.phase === 'complete'
                  ? 'bg-olive-500'
                  : 'bg-aura-500'
            }`}
            style={{ width: `${progress.progress}%` }}
          />
        </div>
      </div>

      {/* Step indicator */}
      {progress.totalSteps > 0 && (
        <div className="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400">
          <ClockIcon className="w-4 h-4" />
          <span>
            Step {progress.currentStep} of {progress.totalSteps}
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * Service boundary card component
 */
function ServiceBoundaryCard({ boundary }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <ServerStackIcon className="w-5 h-5 text-aura-500" />
          <h4 className="font-medium text-surface-900 dark:text-surface-100">
            {boundary.name}
          </h4>
        </div>
        <ConfidenceBadge score={boundary.confidence} size="sm" />
      </div>

      {boundary.description && (
        <p className="text-sm text-surface-600 dark:text-surface-400 mb-3">
          {boundary.description}
        </p>
      )}

      <div className="flex flex-wrap gap-4 text-sm">
        <div className="flex items-center gap-1.5 text-surface-500 dark:text-surface-400">
          <CircleStackIcon className="w-4 h-4" />
          <span>{boundary.nodeCount || boundary.nodes?.length || 0} nodes</span>
        </div>
        {boundary.entryPoints?.length > 0 && (
          <div className="flex items-center gap-1.5 text-surface-500 dark:text-surface-400">
            <ArrowsRightLeftIcon className="w-4 h-4" />
            <span>{boundary.entryPoints.length} entry points</span>
          </div>
        )}
      </div>

      {/* Node list (collapsed) */}
      {boundary.nodes?.length > 0 && (
        <details className="mt-3">
          <summary className="text-sm text-aura-600 dark:text-aura-400 cursor-pointer hover:underline">
            View nodes ({boundary.nodes.length})
          </summary>
          <div className="mt-2 flex flex-wrap gap-1">
            {boundary.nodes.slice(0, 10).map((node, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs bg-surface-100 dark:bg-surface-700 rounded text-surface-600 dark:text-surface-400 font-mono"
              >
                {node}
              </span>
            ))}
            {boundary.nodes.length > 10 && (
              <span className="px-2 py-0.5 text-xs text-surface-500">
                +{boundary.nodes.length - 10} more
              </span>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

/**
 * Technical report section renderer
 */
function ReportSection({ title, content, confidence = null }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-5">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-semibold text-surface-900 dark:text-surface-100">{title}</h4>
        {confidence !== null && <ConfidenceBadge score={confidence} size="sm" />}
      </div>
      <div className="prose prose-sm dark:prose-invert max-w-none">
        {typeof content === 'string' ? (
          <p className="text-surface-600 dark:text-surface-400 whitespace-pre-wrap">{content}</p>
        ) : (
          content
        )}
      </div>
    </div>
  );
}

/**
 * Feedback panel for calibration
 */
function FeedbackPanel({ onSubmit, loading = false }) {
  const [rating, setRating] = useState(null);
  const [comment, setComment] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async () => {
    if (rating === null) return;

    try {
      await onSubmit({
        rating,
        comment: comment.trim() || undefined,
      });
      setSubmitted(true);
    } catch {
      // Error handled by parent
    }
  };

  if (submitted) {
    return (
      <div className="bg-olive-50 dark:bg-olive-900/20 rounded-lg p-4 flex items-center gap-3">
        <CheckCircleIcon className="w-5 h-5 text-olive-600 dark:text-olive-400" />
        <span className="text-olive-700 dark:text-olive-300">
          Thank you for your feedback!
        </span>
      </div>
    );
  }

  return (
    <div className="bg-surface-50 dark:bg-surface-800/50 rounded-lg p-4">
      <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-3">
        Rate this documentation
      </h4>
      <div className="flex items-center gap-3 mb-3">
        <button
          onClick={() => setRating('positive')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
            rating === 'positive'
              ? 'bg-olive-100 border-olive-300 text-olive-700 dark:bg-olive-900/30 dark:border-olive-700 dark:text-olive-400'
              : 'border-surface-200 dark:border-surface-700 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'
          }`}
        >
          <HandThumbUpIcon className="w-5 h-5" />
          Helpful
        </button>
        <button
          onClick={() => setRating('negative')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
            rating === 'negative'
              ? 'bg-critical-100 border-critical-300 text-critical-700 dark:bg-critical-900/30 dark:border-critical-700 dark:text-critical-400'
              : 'border-surface-200 dark:border-surface-700 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'
          }`}
        >
          <HandThumbDownIcon className="w-5 h-5" />
          Not Helpful
        </button>
      </div>

      {rating !== null && (
        <>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Optional: Tell us how we can improve..."
            rows={2}
            className="w-full px-3 py-2 text-sm border border-surface-200 dark:border-surface-700 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder-surface-400 dark:placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-aura-500/50 mb-3"
          />
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? 'Submitting...' : 'Submit Feedback'}
          </button>
        </>
      )}
    </div>
  );
}

/**
 * Export report as PDF document with professional SVG-style graphics
 */
function exportReportToPdf(report, confidence, repositoryName = 'Repository') {
  const pdf = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
  });

  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 15;
  const contentWidth = pageWidth - margin * 2;
  let yPosition = margin;

  // Professional muted color palette
  const colors = {
    text: [33, 37, 41],           // Near black
    textMuted: [108, 117, 125],   // Gray-600
    textLight: [173, 181, 189],   // Gray-400
    border: [222, 226, 230],      // Gray-300
    borderDark: [173, 181, 189],  // Gray-400
    background: [248, 249, 250],  // Gray-100
    white: [255, 255, 255],
    accent: [66, 133, 244],       // Subtle blue
    accentLight: [232, 240, 254], // Very light blue
  };

  // Helper: Check page break
  const checkPageBreak = (requiredHeight) => {
    if (yPosition + requiredHeight > pageHeight - margin - 10) {
      pdf.addPage();
      yPosition = margin;
      return true;
    }
    return false;
  };

  // Helper: Wrap text
  const wrapText = (text, maxWidth, fontSize) => {
    pdf.setFontSize(fontSize);
    return pdf.splitTextToSize(text, maxWidth);
  };

  // Helper: Draw a clean box with optional title
  const drawBox = (x, y, w, h, title = null, items = [], options = {}) => {
    const {
      fillColor = colors.white,
      borderColor = colors.border,
      titleBg = colors.background,
      radius = 1.5
    } = options;

    // Box background
    pdf.setFillColor(...fillColor);
    pdf.setDrawColor(...borderColor);
    pdf.setLineWidth(0.3);
    pdf.roundedRect(x, y, w, h, radius, radius, 'FD');

    let textY = y + 5;

    // Title bar
    if (title) {
      pdf.setFillColor(...titleBg);
      pdf.roundedRect(x + 0.5, y + 0.5, w - 1, 7, radius, radius, 'F');
      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(8);
      pdf.setTextColor(...colors.text);
      pdf.text(title, x + w / 2, y + 5, { align: 'center' });
      textY = y + 11;
    }

    // Items
    if (items.length > 0) {
      pdf.setFont('helvetica', 'normal');
      pdf.setFontSize(6.5);
      pdf.setTextColor(...colors.textMuted);
      items.forEach((item, i) => {
        pdf.text(item, x + 3, textY + i * 4);
      });
    }
  };

  // Helper: Draw connecting line with arrow
  const drawConnector = (x1, y1, x2, y2, options = {}) => {
    const { dashed = false, arrow = true } = options;

    pdf.setDrawColor(...colors.borderDark);
    pdf.setLineWidth(0.4);

    if (dashed) {
      pdf.setLineDashPattern([1, 1], 0);
    }

    pdf.line(x1, y1, x2, y2);

    if (dashed) {
      pdf.setLineDashPattern([], 0);
    }

    // Arrow head
    if (arrow) {
      const angle = Math.atan2(y2 - y1, x2 - x1);
      const arrowSize = 1.5;
      pdf.setFillColor(...colors.borderDark);
      pdf.triangle(
        x2, y2,
        x2 - arrowSize * Math.cos(angle - Math.PI / 6), y2 - arrowSize * Math.sin(angle - Math.PI / 6),
        x2 - arrowSize * Math.cos(angle + Math.PI / 6), y2 - arrowSize * Math.sin(angle + Math.PI / 6),
        'F'
      );
    }
  };

  // Helper: Draw horizontal arrow between boxes
  const drawHorizontalArrow = (x1, y, x2) => {
    pdf.setDrawColor(...colors.borderDark);
    pdf.setLineWidth(0.4);
    pdf.line(x1, y, x2 - 1.5, y);

    // Arrow head
    pdf.setFillColor(...colors.borderDark);
    pdf.triangle(x2, y, x2 - 2, y - 1, x2 - 2, y + 1, 'F');
  };

  // === PAGE 1: HEADER ===
  // Clean header with subtle accent line
  pdf.setFillColor(...colors.accent);
  pdf.rect(0, 0, pageWidth, 2, 'F');

  yPosition = 12;

  // Title
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(18);
  pdf.setTextColor(...colors.text);
  pdf.text('Architecture Documentation', margin, yPosition);

  // Subtitle
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(10);
  pdf.setTextColor(...colors.textMuted);
  pdf.text(repositoryName, margin, yPosition + 6);

  // Confidence indicator (right side)
  if (confidence !== null) {
    const confidencePercent = Math.round(confidence * 100);
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(20);
    pdf.setTextColor(...colors.text);
    pdf.text(`${confidencePercent}%`, pageWidth - margin, yPosition, { align: 'right' });
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7);
    pdf.setTextColor(...colors.textMuted);
    pdf.text('Confidence Score', pageWidth - margin, yPosition + 5, { align: 'right' });
  }

  // Date
  const dateStr = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric'
  });
  pdf.setFontSize(7);
  pdf.setTextColor(...colors.textLight);
  pdf.text(dateStr, pageWidth - margin, yPosition + 10, { align: 'right' });

  yPosition = 30;

  // Divider line
  pdf.setDrawColor(...colors.border);
  pdf.setLineWidth(0.3);
  pdf.line(margin, yPosition, pageWidth - margin, yPosition);

  yPosition += 8;

  // === ARCHITECTURE DIAGRAM ===
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(10);
  pdf.setTextColor(...colors.text);
  pdf.text('System Architecture', margin, yPosition);
  yPosition += 6;

  // Diagram dimensions
  const diagramStartY = yPosition;
  const boxWidth = 50;
  const boxHeight = 28;
  const smallBoxWidth = 52;
  const smallBoxHeight = 32;
  const centerX = pageWidth / 2;

  // === AGENT ORCHESTRATOR (Top) ===
  const orchestratorWidth = 140;
  const orchestratorX = centerX - orchestratorWidth / 2;
  drawBox(orchestratorX, yPosition, orchestratorWidth, 18, 'AGENT ORCHESTRATOR', [
    'Workflow: INIT → PLANNING → CONTEXT → CODE_GEN → REVIEW → VALIDATE'
  ], { fillColor: colors.accentLight, borderColor: colors.accent });

  // Connector lines down from orchestrator
  const orchestratorBottomY = yPosition + 18;
  const agentRowY = yPosition + 30;

  // Vertical lines from orchestrator to agents
  pdf.setDrawColor(...colors.borderDark);
  pdf.setLineWidth(0.4);

  // Left connector
  pdf.line(centerX - 45, orchestratorBottomY, centerX - 45, agentRowY);
  // Center connector
  pdf.line(centerX, orchestratorBottomY, centerX, agentRowY);
  // Right connector
  pdf.line(centerX + 45, orchestratorBottomY, centerX + 45, agentRowY);

  yPosition = agentRowY;

  // === AGENT BOXES (Middle Row) ===
  const agentY = yPosition;
  const agentSpacing = 58;

  // Coder Agent
  drawBox(centerX - agentSpacing - smallBoxWidth / 2, agentY, smallBoxWidth, smallBoxHeight,
    'CODER AGENT', ['• Patch generation', '• Confidence scoring', '• CoD prompts', '• Memory']);

  // Reviewer Agent
  drawBox(centerX - smallBoxWidth / 2, agentY, smallBoxWidth, smallBoxHeight,
    'REVIEWER AGENT', ['• OWASP Top 10', '• Compliance checks', '• Self-reflection', '• Constitutional AI']);

  // Validator Agent
  drawBox(centerX + agentSpacing - smallBoxWidth / 2, agentY, smallBoxWidth, smallBoxHeight,
    'VALIDATOR AGENT', ['• Syntax validation', '• Unit tests', '• Security scans', '• Performance']);

  // Horizontal arrows between agents
  drawHorizontalArrow(centerX - agentSpacing + smallBoxWidth / 2, agentY + smallBoxHeight / 2,
    centerX - smallBoxWidth / 2);
  drawHorizontalArrow(centerX + smallBoxWidth / 2, agentY + smallBoxHeight / 2,
    centerX + agentSpacing - smallBoxWidth / 2);

  yPosition = agentY + smallBoxHeight + 8;

  // Vertical connectors to infrastructure
  const infraY = yPosition + 4;
  pdf.line(centerX - 30, agentY + smallBoxHeight, centerX - 30, infraY);
  pdf.line(centerX + 30, agentY + smallBoxHeight, centerX + 30, infraY);

  yPosition = infraY;

  // === INFRASTRUCTURE BOXES (Bottom Row) ===
  const infraWidth = 55;
  const infraHeight = 30;
  const infraSpacing = 35;

  // Hybrid GraphRAG
  drawBox(centerX - infraSpacing - infraWidth / 2, yPosition, infraWidth, infraHeight,
    'HYBRID GRAPHRAG', ['Neptune (Graph)', 'OpenSearch (Vector)', 'BM25 (Sparse)', 'RRF Fusion']);

  // Sandbox Network
  drawBox(centerX + infraSpacing - infraWidth / 2, yPosition, infraWidth, infraHeight,
    'SANDBOX NETWORK', ['ECS Fargate isolation', '5-layer validation', 'Mock services', 'Synthetic data only']);

  yPosition += infraHeight + 12;

  // === EXECUTIVE SUMMARY ===
  checkPageBreak(40);
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(10);
  pdf.setTextColor(...colors.text);
  pdf.text('Executive Summary', margin, yPosition);
  yPosition += 5;

  if (report.executiveSummary) {
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    pdf.setTextColor(...colors.textMuted);
    const summaryLines = wrapText(report.executiveSummary, contentWidth, 8);
    summaryLines.forEach((line) => {
      checkPageBreak(5);
      pdf.text(line, margin, yPosition);
      yPosition += 4;
    });
  }
  yPosition += 6;

  // === SERVICE INVENTORY ===
  if (report.serviceInventory) {
    checkPageBreak(30);
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(10);
    pdf.setTextColor(...colors.text);
    pdf.text('Service Inventory', margin, yPosition);
    yPosition += 5;

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    pdf.setTextColor(...colors.textMuted);
    const inventoryLines = wrapText(report.serviceInventory, contentWidth, 8);
    inventoryLines.forEach((line) => {
      checkPageBreak(5);
      pdf.text(line, margin, yPosition);
      yPosition += 4;
    });
    yPosition += 6;
  }

  // === DATA FLOW ANALYSIS ===
  if (report.dataFlowAnalysis) {
    checkPageBreak(30);
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(10);
    pdf.setTextColor(...colors.text);
    pdf.text('Data Flow Analysis', margin, yPosition);
    yPosition += 5;

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    pdf.setTextColor(...colors.textMuted);
    const flowLines = wrapText(report.dataFlowAnalysis, contentWidth, 8);
    flowLines.forEach((line) => {
      checkPageBreak(5);
      pdf.text(line, margin, yPosition);
      yPosition += 4;
    });
    yPosition += 6;
  }

  // === SECURITY CONSIDERATIONS ===
  if (report.securityConsiderations) {
    checkPageBreak(25);
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(10);
    pdf.setTextColor(...colors.text);
    pdf.text('Security Considerations', margin, yPosition);
    yPosition += 5;

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    const securityItems = Array.isArray(report.securityConsiderations)
      ? report.securityConsiderations
      : [report.securityConsiderations];
    securityItems.forEach((item) => {
      checkPageBreak(5);
      pdf.setTextColor(...colors.accent);
      pdf.text('•', margin, yPosition);
      pdf.setTextColor(...colors.textMuted);
      const itemLines = wrapText(item, contentWidth - 5, 8);
      itemLines.forEach((line, idx) => {
        pdf.text(line, margin + 4, yPosition + idx * 4);
      });
      yPosition += itemLines.length * 4 + 1;
    });
    yPosition += 4;
  }

  // === RECOMMENDATIONS ===
  if (report.recommendations) {
    checkPageBreak(25);
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(10);
    pdf.setTextColor(...colors.text);
    pdf.text('Recommendations', margin, yPosition);
    yPosition += 5;

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    const recItems = Array.isArray(report.recommendations)
      ? report.recommendations
      : [report.recommendations];
    recItems.forEach((item) => {
      checkPageBreak(5);
      pdf.setTextColor(...colors.accent);
      pdf.text('•', margin, yPosition);
      pdf.setTextColor(...colors.textMuted);
      const itemLines = wrapText(item, contentWidth - 5, 8);
      itemLines.forEach((line, idx) => {
        pdf.text(line, margin + 4, yPosition + idx * 4);
      });
      yPosition += itemLines.length * 4 + 1;
    });
  }

  // === FOOTER on all pages ===
  const totalPages = pdf.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    pdf.setPage(i);

    // Footer line
    pdf.setDrawColor(...colors.border);
    pdf.setLineWidth(0.2);
    pdf.line(margin, pageHeight - 12, pageWidth - margin, pageHeight - 12);

    // Footer text
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7);
    pdf.setTextColor(...colors.textLight);
    pdf.text('Project Aura', margin, pageHeight - 8);
    pdf.text(`${i} / ${totalPages}`, pageWidth - margin, pageHeight - 8, { align: 'right' });
  }

  // Save
  const filename = `${repositoryName.replace(/[^a-z0-9]/gi, '_')}_architecture.pdf`;
  pdf.save(filename);
}

/**
 * Main DocumentationDashboard component
 */
export default function DocumentationDashboard({
  repositories: externalRepositories = [],
  selectedRepository = null,
  onRepositoryChange = null,
}) {
  const [activeTab, setActiveTab] = useState('diagrams');
  const [selectedDiagramTypes, setSelectedDiagramTypes] = useState(['architecture', 'data_flow']);
  const { toast } = useToast();

  // Use mock repositories if none provided
  const repositories = externalRepositories.length > 0 ? externalRepositories : MOCK_REPOSITORIES;
  const [repoId, setRepoId] = useState(selectedRepository?.repository_id || repositories[0]?.repository_id || '');

  const {
    generate,
    cancel,
    clear,
    result,
    diagrams,
    report,
    serviceBoundaries,
    confidence,
    confidenceLevel,
    progress,
    isGenerating,
    isComplete,
    loading,
    error,
    hasError,
    submitFeedback,
    diagramTypes: availableDiagramTypes,
    diagramTypesLoading,
  } = useDocumentationData();

  // Sync with external repository selection
  useEffect(() => {
    if (selectedRepository?.repository_id && selectedRepository.repository_id !== repoId) {
      setRepoId(selectedRepository.repository_id);
    }
  }, [selectedRepository, repoId]);

  // Handle generation
  const handleGenerate = useCallback(async () => {
    // Validate inputs
    if (!repoId) {
      toast.error('Please select a repository');
      return;
    }
    if (selectedDiagramTypes.length === 0) {
      toast.error('Please select at least one diagram type');
      return;
    }

    try {
      // Code Analysis mode → Mermaid generation
      await generate(repoId, {
        mode: 'CODE_ANALYSIS',
        diagramTypes: selectedDiagramTypes,
        includeReport: true,
        renderEngine: 'mermaid',
      });
      toast.success('Documentation generated successfully');
    } catch (err) {
      toast.error(err.message || 'Failed to generate documentation');
    }
  }, [repoId, selectedDiagramTypes, generate, toast]);

  // Handle cancel
  const handleCancel = useCallback(() => {
    cancel();
    toast.info('Generation cancelled');
  }, [cancel, toast]);

  // Handle diagram type toggle
  const toggleDiagramType = (type) => {
    setSelectedDiagramTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  // Handle feedback
  const handleFeedback = useCallback(
    async (feedback) => {
      try {
        await submitFeedback(feedback);
        toast.success('Feedback submitted');
      } catch (err) {
        toast.error('Failed to submit feedback');
        throw err;
      }
    },
    [submitFeedback, toast]
  );

  // Tab configuration
  const tabs = [
    {
      id: 'diagrams',
      label: 'Diagrams',
      icon: CubeTransparentIcon,
      count: diagrams.length,
    },
    {
      id: 'report',
      label: 'Report',
      icon: DocumentTextIcon,
      disabled: !report,
    },
    {
      id: 'boundaries',
      label: 'Service Boundaries',
      icon: ServerStackIcon,
      count: serviceBoundaries.length,
    },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                Documentation Generator
              </h1>
              <p className="mt-1 text-surface-500 dark:text-surface-400">
                Generate architecture diagrams and technical documentation from code analysis
              </p>
            </div>

            {isComplete && confidence !== null && (
              <div className="flex items-center gap-4">
                <ConfidenceGauge
                  score={confidence}
                  size={120}
                  strokeWidth={10}
                  showLabel={false}
                  showDescription={false}
                />
              </div>
            )}
          </div>
        </div>

        {/* Configuration Panel */}
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-6 mb-6">
          {/* Repository Selection */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Repository
            </label>
            {repositories.length > 0 ? (
              <select
                value={repoId}
                onChange={(e) => {
                  setRepoId(e.target.value);
                  if (onRepositoryChange) {
                    const repo = repositories.find((r) => r.repository_id === e.target.value);
                    onRepositoryChange(repo);
                  }
                }}
                disabled={isGenerating}
                className="w-full px-3 py-2 border border-surface-200 dark:border-surface-700 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500/50 disabled:opacity-50 max-w-md"
              >
                <option value="">Select a repository...</option>
                {repositories.map((repo) => (
                  <option key={repo.repository_id} value={repo.repository_id}>
                    {repo.name || repo.repository_id}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={repoId}
                onChange={(e) => setRepoId(e.target.value)}
                placeholder="Enter repository ID..."
                disabled={isGenerating}
                className="w-full px-3 py-2 border border-surface-200 dark:border-surface-700 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-aura-500/50 disabled:opacity-50 max-w-md"
              />
            )}
            <p className="mt-2 text-xs text-surface-500 dark:text-surface-400">
              Analyze repository code to generate Mermaid diagrams
            </p>
          </div>

          {/* Diagram Type Selection */}
          <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-3">
                Diagram Types
              </label>
              <div className="flex flex-wrap gap-2">
                {diagramTypesLoading ? (
                  <>
                    <Skeleton className="w-24 h-9 rounded-lg" />
                    <Skeleton className="w-28 h-9 rounded-lg" />
                    <Skeleton className="w-32 h-9 rounded-lg" />
                  </>
                ) : (
                  Object.entries(DIAGRAM_TYPE_INFO).map(([type, info]) => {
                    const isSelected = selectedDiagramTypes.includes(type);
                    const Icon = info.icon;

                    return (
                      <button
                        key={type}
                        onClick={() => toggleDiagramType(type)}
                        disabled={isGenerating}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors disabled:opacity-50 ${
                          isSelected
                            ? 'bg-aura-100 border-aura-300 text-aura-700 dark:bg-aura-900/30 dark:border-aura-700 dark:text-aura-400'
                            : 'bg-white dark:bg-surface-800 border-surface-200 dark:border-surface-700 text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700'
                        }`}
                        title={info.description}
                      >
                        <Icon className="w-4 h-4" />
                        {info.label}
                      </button>
                    );
                  })
                )}
              </div>
          </div>

          {/* Generate Button */}
          <div className="mt-6 flex items-center gap-4">
            {isGenerating ? (
              <button
                onClick={handleCancel}
                className="flex items-center gap-2 px-6 py-2.5 text-sm font-medium text-white bg-critical-600 hover:bg-critical-700 rounded-lg transition-colors"
              >
                <StopIcon className="w-4 h-4" />
                Cancel Generation
              </button>
            ) : (
              <button
                onClick={handleGenerate}
                disabled={!repoId || selectedDiagramTypes.length === 0}
                className="flex items-center gap-2 px-6 py-2.5 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <PlayIcon className="w-4 h-4" />
                Generate Documentation
              </button>
            )}
          </div>
        </div>

        {/* Progress Indicator */}
        {isGenerating && (
          <div className="mb-6">
            <GenerationProgress progress={progress} onCancel={handleCancel} />
          </div>
        )}

        {/* Error Display */}
        {hasError && (
          <div className="mb-6 p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg flex items-start gap-3">
            <ExclamationTriangleIcon className="w-5 h-5 text-critical-600 dark:text-critical-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-critical-800 dark:text-critical-200">
                Generation Failed
              </p>
              <p className="text-sm text-critical-600 dark:text-critical-400 mt-1">
                {error?.message || 'An error occurred during documentation generation.'}
              </p>
              <button
                onClick={clear}
                className="mt-2 text-sm text-critical-700 dark:text-critical-300 hover:underline"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Results Section */}
        {isComplete && result && (
          <>
            {/* Tabs */}
            <div className="border-b border-surface-200 dark:border-surface-700 mb-6">
              <nav className="flex gap-6" role="tablist">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      disabled={tab.disabled}
                      role="tab"
                      aria-selected={activeTab === tab.id}
                      aria-controls={`tabpanel-${tab.id}`}
                      className={`
                        flex items-center gap-2 pb-3 text-sm font-medium border-b-2 transition-colors
                        ${
                          activeTab === tab.id
                            ? 'border-aura-500 text-aura-600 dark:text-aura-400'
                            : 'border-transparent text-surface-500 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-200'
                        }
                        ${tab.disabled ? 'opacity-50 cursor-not-allowed' : ''}
                      `}
                    >
                      <Icon className="w-4 h-4" />
                      {tab.label}
                      {tab.count !== undefined && tab.count > 0 && (
                        <span className="ml-1 px-1.5 py-0.5 text-xs bg-surface-100 dark:bg-surface-700 rounded-full">
                          {tab.count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Tab Content */}
            <div
              id={`tabpanel-${activeTab}`}
              role="tabpanel"
              aria-labelledby={`tab-${activeTab}`}
            >
              {/* Diagrams Tab */}
              {activeTab === 'diagrams' && (
                <div className="space-y-6">
                  {diagrams.length > 0 ? (
                    <>
                      {diagrams.length === 1 ? (
                        <DiagramViewer
                          code={diagrams[0].mermaidCode}
                          svgContent={diagrams[0].svgContent}
                          dslContent={diagrams[0].dslContent}
                          renderEngine={diagrams[0].renderEngine}
                          type={diagrams[0].diagramType}
                          confidence={diagrams[0].confidence}
                          warnings={diagrams[0].warnings}
                        />
                      ) : (
                        <DiagramGrid
                          diagrams={diagrams}
                          columns={diagrams.length <= 2 ? diagrams.length : 2}
                        />
                      )}

                      {/* Export Options */}
                      <div className="flex items-center gap-3 pt-4 border-t border-surface-200 dark:border-surface-700">
                        <span className="text-sm text-surface-500 dark:text-surface-400">
                          Export:
                        </span>
                        {diagrams.map((diagram) => (
                          <button
                            key={diagram.diagramType}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
                          >
                            <ArrowDownTrayIcon className="w-4 h-4" />
                            {DIAGRAM_TYPE_INFO[diagram.diagramType]?.label || diagram.diagramType}
                          </button>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-12 text-surface-500 dark:text-surface-400">
                      <ChartBarIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No diagrams generated</p>
                    </div>
                  )}
                </div>
              )}

              {/* Report Tab */}
              {activeTab === 'report' && report && (
                <div className="space-y-6">
                  {/* Export Button */}
                  <div className="flex justify-end">
                    <button
                      onClick={() => {
                        const repoName = repositories.find(r => r.repository_id === repoId)?.name || repoId;
                        exportReportToPdf(report, confidence, repoName);
                      }}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 rounded-lg transition-colors"
                    >
                      <ArrowDownTrayIcon className="w-4 h-4" />
                      Export PDF
                    </button>
                  </div>

                  {/* Executive Summary */}
                  {report.executiveSummary && (
                    <ReportSection
                      title="Executive Summary"
                      content={report.executiveSummary}
                      confidence={report.summaryConfidence}
                    />
                  )}

                  {/* Service Inventory */}
                  {report.serviceInventory && (
                    <ReportSection
                      title="Service Inventory"
                      content={report.serviceInventory}
                    />
                  )}

                  {/* Data Flow Analysis */}
                  {report.dataFlowAnalysis && (
                    <ReportSection
                      title="Data Flow Analysis"
                      content={report.dataFlowAnalysis}
                    />
                  )}

                  {/* Security Considerations */}
                  {report.securityConsiderations && (
                    <ReportSection
                      title="Security Considerations"
                      content={
                        <ul className="list-disc list-inside space-y-1 text-surface-600 dark:text-surface-400">
                          {(Array.isArray(report.securityConsiderations)
                            ? report.securityConsiderations
                            : [report.securityConsiderations]
                          ).map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      }
                    />
                  )}

                  {/* Recommendations */}
                  {report.recommendations && (
                    <ReportSection
                      title="Recommendations"
                      content={
                        <ul className="list-disc list-inside space-y-1 text-surface-600 dark:text-surface-400">
                          {(Array.isArray(report.recommendations)
                            ? report.recommendations
                            : [report.recommendations]
                          ).map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      }
                    />
                  )}

                  {/* Overall Confidence */}
                  <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-5">
                    <h4 className="font-semibold text-surface-900 dark:text-surface-100 mb-4">
                      Confidence Analysis
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <ConfidenceBar score={confidence} showLabel />
                      <div className="flex items-start gap-2 text-sm text-surface-500 dark:text-surface-400">
                        <InformationCircleIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
                        <p>
                          Confidence scores indicate how certain the analysis is based on available
                          code context. Lower scores may require manual verification.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Feedback */}
                  <FeedbackPanel onSubmit={handleFeedback} loading={loading} />
                </div>
              )}

              {/* Service Boundaries Tab */}
              {activeTab === 'boundaries' && (
                <div className="space-y-4">
                  {serviceBoundaries.length > 0 ? (
                    <>
                      <div className="flex items-center justify-between mb-4">
                        <p className="text-sm text-surface-600 dark:text-surface-400">
                          Detected {serviceBoundaries.length} service{' '}
                          {serviceBoundaries.length === 1 ? 'boundary' : 'boundaries'} using Louvain
                          community detection algorithm.
                        </p>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {serviceBoundaries.map((boundary, index) => (
                          <ServiceBoundaryCard
                            key={boundary.boundaryId || index}
                            boundary={boundary}
                          />
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-12 text-surface-500 dark:text-surface-400">
                      <ServerStackIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No service boundaries detected</p>
                      <p className="text-sm mt-1">
                        This may indicate a monolithic architecture or insufficient code context.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}

        {/* Empty State */}
        {!isGenerating && !isComplete && !hasError && (
          <div className="text-center py-16 bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
            <CubeTransparentIcon className="w-16 h-16 mx-auto mb-4 text-surface-300 dark:text-surface-600" />
            <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100 mb-2">
              Generate Documentation
            </h3>
            <p className="text-surface-500 dark:text-surface-400 max-w-md mx-auto">
              Select a repository and diagram types, then click Generate to create architecture
              diagrams and technical documentation using Mermaid.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
