/**
 * Project Aura - DiagramExportPanel Component (ADR-060 Phase 4)
 *
 * Panel for exporting diagrams to multiple formats: SVG, PNG, PDF, draw.io.
 * Supports configurable export options and direct download.
 *
 * Design System: Apple-inspired with clean typography, generous spacing,
 * and smooth transitions per design-principles.md
 */

import { useState, useCallback, useMemo } from 'react';
import { useTheme } from '../../context/ThemeContext';
import {
  ArrowDownTrayIcon,
  DocumentIcon,
  PhotoIcon,
  DocumentTextIcon,
  ArrowPathIcon,
  CheckIcon,
  AdjustmentsHorizontalIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';

// ============================================================================
// Constants
// ============================================================================

const EXPORT_FORMATS = {
  svg: {
    id: 'svg',
    label: 'SVG',
    description: 'Scalable vector graphics',
    extension: '.svg',
    mimeType: 'image/svg+xml',
    icon: DocumentIcon,
    color: 'text-orange-500',
  },
  png: {
    id: 'png',
    label: 'PNG',
    description: 'Raster image (high quality)',
    extension: '.png',
    mimeType: 'image/png',
    icon: PhotoIcon,
    color: 'text-blue-500',
  },
  pdf: {
    id: 'pdf',
    label: 'PDF',
    description: 'Document format',
    extension: '.pdf',
    mimeType: 'application/pdf',
    icon: DocumentTextIcon,
    color: 'text-red-500',
  },
  drawio: {
    id: 'drawio',
    label: 'draw.io',
    description: 'Edit in diagrams.net',
    extension: '.drawio',
    mimeType: 'application/xml',
    icon: DocumentIcon,
    color: 'text-green-500',
  },
};

const EXPORT_STATUS = {
  idle: 'idle',
  exporting: 'exporting',
  success: 'success',
  error: 'error',
};

const SCALE_OPTIONS = [
  { value: 0.5, label: '0.5x' },
  { value: 1, label: '1x' },
  { value: 2, label: '2x' },
  { value: 3, label: '3x' },
  { value: 4, label: '4x' },
];

const BACKGROUND_OPTIONS = [
  { value: null, label: 'Transparent' },
  { value: '#FFFFFF', label: 'White' },
  { value: '#000000', label: 'Black' },
  { value: '#F3F4F6', label: 'Light Gray' },
  { value: '#1F2937', label: 'Dark Gray' },
];

// ============================================================================
// FormatCard Component
// ============================================================================

function FormatCard({ format, isSelected, onSelect, isExporting, status }) {
  const Icon = format.icon;

  return (
    <button
      onClick={() => onSelect(format.id)}
      disabled={isExporting}
      className={`
        relative flex items-center gap-3 p-4 rounded-xl border-2
        transition-all duration-200
        ${
          isSelected
            ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
            : 'border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-700'
        }
        ${isExporting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      <div
        className={`
        w-10 h-10 rounded-lg flex items-center justify-center
        ${isSelected ? 'bg-aura-100 dark:bg-aura-800' : 'bg-surface-100 dark:bg-surface-700'}
      `}
      >
        <Icon className={`w-5 h-5 ${format.color}`} />
      </div>
      <div className="flex-1 text-left">
        <div className="font-medium text-surface-900 dark:text-white">{format.label}</div>
        <div className="text-xs text-surface-500">{format.description}</div>
      </div>
      {isSelected && status === EXPORT_STATUS.success && (
        <CheckIcon className="w-5 h-5 text-green-500" />
      )}
      {isSelected && status === EXPORT_STATUS.exporting && (
        <ArrowPathIcon className="w-5 h-5 text-aura-500 animate-spin" />
      )}
    </button>
  );
}

// ============================================================================
// ExportOptions Component
// ============================================================================

function ExportOptions({
  format,
  scale,
  onScaleChange,
  backgroundColor,
  onBackgroundColorChange,
  includeMetadata,
  onIncludeMetadataChange,
  padding,
  onPaddingChange,
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Not all options apply to all formats
  const showScaleOption = format === 'png' || format === 'pdf';
  const showBackgroundOption = format === 'png' || format === 'svg';
  const showMetadataOption = format === 'svg' || format === 'drawio';

  if (!showScaleOption && !showBackgroundOption && !showMetadataOption) {
    return null;
  }

  return (
    <div className="border border-surface-200 dark:border-surface-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="
          w-full flex items-center justify-between px-4 py-3
          bg-surface-50 dark:bg-surface-800
          text-surface-700 dark:text-surface-300
          hover:bg-surface-100 dark:hover:bg-surface-700
          transition-colors
        "
      >
        <span className="flex items-center gap-2 text-sm font-medium">
          <AdjustmentsHorizontalIcon className="w-4 h-4" />
          Export Options
        </span>
        {isExpanded ? (
          <ChevronUpIcon className="w-4 h-4" />
        ) : (
          <ChevronDownIcon className="w-4 h-4" />
        )}
      </button>

      {isExpanded && (
        <div className="p-4 space-y-4 bg-white dark:bg-surface-900">
          {/* Scale Option */}
          {showScaleOption && (
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                Scale
              </label>
              <div className="flex gap-2">
                {SCALE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => onScaleChange(option.value)}
                    className={`
                      px-3 py-1.5 rounded-lg text-sm font-medium
                      transition-colors duration-200
                      ${
                        scale === option.value
                          ? 'bg-aura-500 text-white'
                          : 'bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-200 dark:hover:bg-surface-600'
                      }
                    `}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Background Color Option */}
          {showBackgroundOption && (
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                Background
              </label>
              <select
                value={backgroundColor || ''}
                onChange={(e) => onBackgroundColorChange(e.target.value || null)}
                className="
                  w-full px-3 py-2 rounded-lg
                  bg-white dark:bg-surface-800
                  border border-surface-200 dark:border-surface-700
                  text-surface-900 dark:text-white
                  focus:outline-none focus:ring-2 focus:ring-aura-500
                "
              >
                {BACKGROUND_OPTIONS.map((option) => (
                  <option key={option.label} value={option.value || ''}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Padding Option */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Padding: {padding}px
            </label>
            <input
              type="range"
              min="0"
              max="100"
              step="10"
              value={padding}
              onChange={(e) => onPaddingChange(parseInt(e.target.value, 10))}
              className="w-full accent-aura-500"
            />
          </div>

          {/* Include Metadata Option */}
          {showMetadataOption && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => onIncludeMetadataChange(!includeMetadata)}
                className={`
                  relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full
                  border-2 border-transparent transition-colors duration-200 ease-in-out
                  focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
                  ${includeMetadata ? 'bg-aura-500' : 'bg-surface-200 dark:bg-surface-700'}
                `}
                role="switch"
                aria-checked={includeMetadata}
              >
                <span
                  className={`
                    pointer-events-none inline-block h-5 w-5 transform rounded-full
                    bg-white shadow ring-0 transition duration-200 ease-in-out
                    ${includeMetadata ? 'translate-x-5' : 'translate-x-0'}
                  `}
                />
              </button>
              <span className="text-sm text-surface-700 dark:text-surface-300">
                Include metadata
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// DiagramExportPanel Component
// ============================================================================

export default function DiagramExportPanel({
  svgContent,
  diagramName = 'diagram',
  onExportStart,
  onExportComplete,
  className = '',
}) {
  const { isDarkMode } = useTheme();

  // State
  const [selectedFormat, setSelectedFormat] = useState('svg');
  const [exportStatus, setExportStatus] = useState(EXPORT_STATUS.idle);
  const [exportError, setExportError] = useState(null);

  // Export options
  const [scale, setScale] = useState(1);
  const [backgroundColor, setBackgroundColor] = useState(null);
  const [includeMetadata, setIncludeMetadata] = useState(true);
  const [padding, setPadding] = useState(20);

  // Format list as array
  const formats = useMemo(() => Object.values(EXPORT_FORMATS), []);

  // Handle export
  const handleExport = useCallback(async () => {
    if (!svgContent) return;

    setExportStatus(EXPORT_STATUS.exporting);
    setExportError(null);
    onExportStart?.();

    try {
      const response = await fetch('/api/v1/diagrams/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          svgContent,
          format: selectedFormat,
          options: {
            scale,
            backgroundColor,
            includeMetadata,
            padding,
          },
          diagramName,
        }),
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      const result = await response.json();

      if (result.success && result.contentBase64) {
        // Trigger download
        const format = EXPORT_FORMATS[selectedFormat];
        const blob = base64ToBlob(result.contentBase64, format.mimeType);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${diagramName}${format.extension}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        setExportStatus(EXPORT_STATUS.success);
        onExportComplete?.(true, result);

        // Reset status after a delay
        setTimeout(() => setExportStatus(EXPORT_STATUS.idle), 2000);
      } else {
        throw new Error(result.error || 'Export failed');
      }
    } catch (error) {
      console.error('Export failed:', error);
      setExportStatus(EXPORT_STATUS.error);
      setExportError(error.message);
      onExportComplete?.(false, { error: error.message });
    }
  }, [
    svgContent,
    selectedFormat,
    scale,
    backgroundColor,
    includeMetadata,
    padding,
    diagramName,
    onExportStart,
    onExportComplete,
  ]);

  // Handle client-side SVG export (for immediate download without server)
  const handleClientSideExport = useCallback(() => {
    if (!svgContent) return;

    const format = EXPORT_FORMATS[selectedFormat];

    if (selectedFormat === 'svg') {
      // Direct SVG download
      const blob = new Blob([svgContent], { type: format.mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${diagramName}${format.extension}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setExportStatus(EXPORT_STATUS.success);
      setTimeout(() => setExportStatus(EXPORT_STATUS.idle), 2000);
    } else {
      // Use server for other formats
      handleExport();
    }
  }, [svgContent, selectedFormat, diagramName, handleExport]);

  const isExporting = exportStatus === EXPORT_STATUS.exporting;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800
        rounded-2xl shadow-lg
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-white flex items-center gap-2">
          <ArrowDownTrayIcon className="w-5 h-5 text-aura-500" />
          Export Diagram
        </h3>
        <p className="mt-1 text-sm text-surface-500">
          Download your diagram in various formats
        </p>
      </div>

      {/* Format Selection */}
      <div className="p-6 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {formats.map((format) => (
            <FormatCard
              key={format.id}
              format={format}
              isSelected={selectedFormat === format.id}
              onSelect={setSelectedFormat}
              isExporting={isExporting}
              status={exportStatus}
            />
          ))}
        </div>

        {/* Export Options */}
        <ExportOptions
          format={selectedFormat}
          scale={scale}
          onScaleChange={setScale}
          backgroundColor={backgroundColor}
          onBackgroundColorChange={setBackgroundColor}
          includeMetadata={includeMetadata}
          onIncludeMetadataChange={setIncludeMetadata}
          padding={padding}
          onPaddingChange={setPadding}
        />

        {/* Error Message */}
        {exportError && (
          <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm">
            {exportError}
          </div>
        )}

        {/* Export Button */}
        <button
          onClick={handleClientSideExport}
          disabled={isExporting || !svgContent}
          className="
            w-full py-3 rounded-xl
            bg-aura-500 text-white font-medium
            hover:bg-aura-600
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors duration-200
            flex items-center justify-center gap-2
          "
        >
          {isExporting ? (
            <>
              <ArrowPathIcon className="w-5 h-5 animate-spin" />
              Exporting...
            </>
          ) : exportStatus === EXPORT_STATUS.success ? (
            <>
              <CheckIcon className="w-5 h-5" />
              Downloaded!
            </>
          ) : (
            <>
              <ArrowDownTrayIcon className="w-5 h-5" />
              Download {EXPORT_FORMATS[selectedFormat].label}
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Helper Functions
// ============================================================================

function base64ToBlob(base64, mimeType) {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: mimeType });
}

// ============================================================================
// Exports
// ============================================================================

export { FormatCard, ExportOptions, EXPORT_FORMATS, base64ToBlob };
