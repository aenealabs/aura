/**
 * Project Aura - DiagramEditor Component
 *
 * DSL-based diagram editor with live preview, syntax validation,
 * and natural language generation support (ADR-060).
 *
 * Design System: Apple-inspired with clean typography, generous spacing,
 * and smooth transitions per design-principles.md
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useTheme } from '../../context/ThemeContext';
import DiagramViewer from './DiagramViewer';
import {
  PlayIcon,
  SparklesIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClipboardDocumentIcon,
  ArrowPathIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  LightBulbIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';

// ============================================================================
// Constants & Configuration
// ============================================================================

const DEFAULT_DSL = `title: My Architecture Diagram
direction: TB

# Groups define containers (VPCs, subnets, etc.)
groups:
  - id: vpc
    label: Production VPC
    children:
      - web-tier
      - app-tier
      - db-tier

# Nodes represent services and resources
nodes:
  - id: users
    label: Users
    icon: generic:user
  - id: web-tier
    label: Web Servers
    icon: aws:ec2
  - id: app-tier
    label: Application
    icon: aws:ecs
  - id: db-tier
    label: Database
    icon: aws:rds

# Connections show data flow
connections:
  - from: users
    to: web-tier
    label: HTTPS
  - from: web-tier
    to: app-tier
    label: HTTP
  - from: app-tier
    to: db-tier
    label: SQL
`;

const EXAMPLE_PROMPTS = [
  'Draw a three-tier web architecture with AWS services',
  'Create a microservices diagram with API gateway and multiple services',
  'Show a CI/CD pipeline from GitHub to EKS',
  'Design a data pipeline with Kinesis, Lambda, and S3',
];

// ============================================================================
// ValidationPanel Component
// ============================================================================

function ValidationPanel({ errors, warnings, isValidating }) {
  const [isExpanded, setIsExpanded] = useState(true);

  const hasIssues = errors.length > 0 || warnings.length > 0;

  if (!hasIssues && !isValidating) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-success-600 dark:text-success-400">
        <CheckCircleIcon className="w-4 h-4" />
        <span>DSL is valid</span>
      </div>
    );
  }

  return (
    <div
      className="
        border-t border-surface-200 dark:border-surface-700
        bg-surface-50 dark:bg-surface-800/50
      "
    >
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="
          flex items-center justify-between w-full
          px-3 py-2
          hover:bg-surface-100 dark:hover:bg-surface-700/50
          transition-colors duration-150
        "
      >
        <div className="flex items-center gap-2">
          {isValidating ? (
            <ArrowPathIcon className="w-4 h-4 text-surface-500 animate-spin" />
          ) : errors.length > 0 ? (
            <ExclamationTriangleIcon className="w-4 h-4 text-critical-500" />
          ) : (
            <ExclamationTriangleIcon className="w-4 h-4 text-warning-500" />
          )}
          <span className="text-sm font-medium text-surface-700 dark:text-surface-200">
            {isValidating ? 'Validating...' : `${errors.length} errors, ${warnings.length} warnings`}
          </span>
        </div>
        {isExpanded ? (
          <ChevronDownIcon className="w-4 h-4 text-surface-400" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 text-surface-400" />
        )}
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 max-h-48 overflow-y-auto">
          {errors.map((error, i) => (
            <div
              key={`error-${i}`}
              className="
                flex items-start gap-2 py-1
                text-sm text-critical-600 dark:text-critical-400
              "
            >
              <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          ))}
          {warnings.map((warning, i) => (
            <div
              key={`warning-${i}`}
              className="
                flex items-start gap-2 py-1
                text-sm text-warning-600 dark:text-warning-400
              "
            >
              <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// NLPromptInput Component
// ============================================================================

function NLPromptInput({ onGenerate, isGenerating }) {
  const [prompt, setPrompt] = useState('');
  const [showExamples, setShowExamples] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (prompt.trim() && !isGenerating) {
      onGenerate(prompt.trim());
    }
  };

  return (
    <div className="space-y-2">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="flex-1 relative">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe your architecture in natural language..."
            className="
              w-full px-4 py-2.5 pr-10
              bg-surface-50 dark:bg-surface-700
              border border-surface-200 dark:border-surface-600
              rounded-lg
              text-sm text-surface-900 dark:text-surface-100
              placeholder:text-surface-400 dark:placeholder:text-surface-500
              focus:outline-none focus:ring-2 focus:ring-aura-500
              transition-all duration-200
            "
            disabled={isGenerating}
          />
          <SparklesIcon
            className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-aura-500"
            aria-hidden="true"
          />
        </div>
        <button
          type="submit"
          disabled={!prompt.trim() || isGenerating}
          className="
            flex items-center gap-2 px-4 py-2.5
            bg-aura-500 hover:bg-aura-600
            disabled:bg-surface-300 dark:disabled:bg-surface-600
            text-white font-medium text-sm
            rounded-lg
            transition-all duration-200
            disabled:cursor-not-allowed
          "
        >
          {isGenerating ? (
            <>
              <ArrowPathIcon className="w-4 h-4 animate-spin" />
              <span>Generating...</span>
            </>
          ) : (
            <>
              <SparklesIcon className="w-4 h-4" />
              <span>Generate</span>
            </>
          )}
        </button>
      </form>

      <button
        onClick={() => setShowExamples(!showExamples)}
        className="
          flex items-center gap-1
          text-xs text-surface-500 dark:text-surface-400
          hover:text-aura-600 dark:hover:text-aura-400
          transition-colors duration-150
        "
      >
        <LightBulbIcon className="w-3.5 h-3.5" />
        <span>{showExamples ? 'Hide examples' : 'Show example prompts'}</span>
      </button>

      {showExamples && (
        <div className="flex flex-wrap gap-2 pt-1">
          {EXAMPLE_PROMPTS.map((example, i) => (
            <button
              key={i}
              onClick={() => setPrompt(example)}
              className="
                px-3 py-1.5
                bg-surface-100 dark:bg-surface-700
                hover:bg-surface-200 dark:hover:bg-surface-600
                border border-surface-200 dark:border-surface-600
                rounded-full
                text-xs text-surface-600 dark:text-surface-300
                transition-colors duration-150
              "
            >
              {example}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// DSLEditor Component
// ============================================================================

function DSLEditor({ value, onChange, onValidate, errors = [] }) {
  const textareaRef = useRef(null);
  const lineNumbersRef = useRef(null);

  // Sync scroll between textarea and line numbers
  const handleScroll = useCallback(() => {
    if (textareaRef.current && lineNumbersRef.current) {
      lineNumbersRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  }, []);

  // Calculate line numbers
  const lineNumbers = useMemo(() => {
    const lines = value.split('\n');
    return lines.map((_, i) => i + 1);
  }, [value]);

  // Get error lines
  const errorLines = useMemo(() => {
    return new Set(errors.map((e) => e.line).filter(Boolean));
  }, [errors]);

  return (
    <div className="relative flex h-full font-mono text-sm">
      {/* Line numbers */}
      <div
        ref={lineNumbersRef}
        className="
          flex-shrink-0 w-12
          bg-surface-100 dark:bg-surface-800
          border-r border-surface-200 dark:border-surface-700
          overflow-hidden
          select-none
        "
        aria-hidden="true"
      >
        <div className="py-3 px-2 text-right">
          {lineNumbers.map((num) => (
            <div
              key={num}
              className={`
                leading-6 h-6
                ${errorLines.has(num)
                  ? 'text-critical-500 bg-critical-100 dark:bg-critical-900/30'
                  : 'text-surface-400 dark:text-surface-500'
                }
              `}
            >
              {num}
            </div>
          ))}
        </div>
      </div>

      {/* Editor textarea */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onValidate}
        onScroll={handleScroll}
        className="
          flex-1 p-3
          bg-white dark:bg-surface-900
          text-surface-900 dark:text-surface-100
          resize-none
          focus:outline-none
          leading-6
        "
        spellCheck={false}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        placeholder="Enter your diagram DSL here..."
        aria-label="Diagram DSL editor"
      />
    </div>
  );
}

// ============================================================================
// Main DiagramEditor Component
// ============================================================================

export default function DiagramEditor({
  initialDsl = DEFAULT_DSL,
  onDslChange,
  onRender,
  apiEndpoint = '/api/diagrams/render',
  className = '',
}) {
  const { isDarkMode } = useTheme();

  // State
  const [dsl, setDsl] = useState(initialDsl);
  const [svgContent, setSvgContent] = useState('');
  const [errors, setErrors] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [isValidating, setIsValidating] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState('dsl'); // 'dsl' | 'nl'

  // Handle DSL change
  const handleDslChange = useCallback(
    (newDsl) => {
      setDsl(newDsl);
      onDslChange?.(newDsl);
    },
    [onDslChange]
  );

  // Validate DSL
  const handleValidate = useCallback(async () => {
    setIsValidating(true);
    try {
      const response = await fetch(`${apiEndpoint}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dsl }),
      });
      const data = await response.json();
      setErrors(data.errors || []);
      setWarnings(data.warnings || []);
    } catch (error) {
      console.error('Validation error:', error);
      setErrors([{ message: 'Failed to validate DSL' }]);
    } finally {
      setIsValidating(false);
    }
  }, [dsl, apiEndpoint]);

  // Render diagram
  const handleRender = useCallback(async () => {
    if (errors.length > 0) {
      return;
    }

    setIsRendering(true);
    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dsl,
          theme: isDarkMode ? 'dark' : 'light',
        }),
      });

      if (!response.ok) {
        throw new Error('Render failed');
      }

      const data = await response.json();
      setSvgContent(data.svg);
      onRender?.(data.svg);
    } catch (error) {
      console.error('Render error:', error);
      setErrors([{ message: 'Failed to render diagram' }]);
    } finally {
      setIsRendering(false);
    }
  }, [dsl, isDarkMode, apiEndpoint, errors.length, onRender]);

  // Generate from natural language
  const handleGenerate = useCallback(
    async (prompt) => {
      setIsGenerating(true);
      try {
        const response = await fetch(`${apiEndpoint}/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt }),
        });

        if (!response.ok) {
          throw new Error('Generation failed');
        }

        const data = await response.json();
        handleDslChange(data.dsl);
        setActiveTab('dsl');
        setSvgContent(data.svg || '');
      } catch (error) {
        console.error('Generation error:', error);
        setErrors([{ message: 'Failed to generate diagram from prompt' }]);
      } finally {
        setIsGenerating(false);
      }
    },
    [apiEndpoint, handleDslChange]
  );

  // Copy DSL to clipboard
  const handleCopyDsl = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(dsl);
    } catch (error) {
      console.error('Copy failed:', error);
    }
  }, [dsl]);

  return (
    <div
      className={`
        grid grid-cols-2 gap-4
        min-h-[600px]
        ${className}
      `}
    >
      {/* Editor Panel */}
      <div
        className="
          flex flex-col
          bg-white dark:bg-surface-800
          border border-surface-200 dark:border-surface-700
          rounded-xl overflow-hidden
        "
      >
        {/* Editor Header */}
        <div
          className="
            flex items-center justify-between
            px-4 py-3
            border-b border-surface-200 dark:border-surface-700
          "
        >
          <div className="flex items-center">
            <button
              onClick={() => setActiveTab('nl')}
              className={`
                flex items-center gap-2 px-3 py-1.5 rounded-lg
                text-sm font-medium
                transition-colors duration-150
                ${activeTab === 'nl'
                  ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300'
                  : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'
                }
              `}
            >
              <SparklesIcon className="w-4 h-4" />
              <span>AI Generate</span>
            </button>
            <button
              onClick={() => setActiveTab('dsl')}
              className={`
                flex items-center gap-2 px-3 py-1.5 rounded-lg
                text-sm font-medium
                transition-colors duration-150
                ${activeTab === 'dsl'
                  ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300'
                  : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'
                }
              `}
            >
              <CommandLineIcon className="w-4 h-4" />
              <span>DSL Editor</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyDsl}
              className="
                p-2 rounded-lg
                hover:bg-surface-100 dark:hover:bg-surface-700
                transition-colors duration-150
              "
              title="Copy DSL"
            >
              <ClipboardDocumentIcon className="w-4 h-4 text-surface-500" />
            </button>
            <button
              onClick={handleRender}
              disabled={isRendering || errors.length > 0}
              className="
                flex items-center gap-2 px-3 py-1.5
                bg-success-500 hover:bg-success-600
                disabled:bg-surface-300 dark:disabled:bg-surface-600
                text-white font-medium text-sm
                rounded-lg
                transition-all duration-200
                disabled:cursor-not-allowed
              "
            >
              {isRendering ? (
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
              ) : (
                <PlayIcon className="w-4 h-4" />
              )}
              <span>Render</span>
            </button>
          </div>
        </div>

        {/* Editor Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'nl' ? (
            <div className="p-4">
              <NLPromptInput onGenerate={handleGenerate} isGenerating={isGenerating} />
            </div>
          ) : (
            <DSLEditor
              value={dsl}
              onChange={handleDslChange}
              onValidate={handleValidate}
              errors={errors}
            />
          )}
        </div>

        {/* Validation Panel */}
        <ValidationPanel
          errors={errors.map((e) => e.message || e)}
          warnings={warnings.map((w) => w.message || w)}
          isValidating={isValidating}
        />
      </div>

      {/* Preview Panel */}
      <DiagramViewer
        svgContent={svgContent}
        title="Preview"
        className="h-full"
      />
    </div>
  );
}
