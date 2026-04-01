/**
 * Finding Detail Drawer (P0)
 *
 * Sliding drawer panel showing full finding details:
 * - Finding header with severity/confidence badges
 * - File location with source link
 * - Affected code with syntax highlighting
 * - LLM reasoning (chain-of-thought)
 * - Suggested fix (side-by-side diff)
 * - Verification status
 * - Dataflow chain visualization
 * - Actions (accept fix, reject, false positive, escalate)
 *
 * Per ADR-084
 *
 * @module components/scanner/FindingDetailDrawer
 */

import { useState, useEffect, useRef } from 'react';
import {
  XMarkIcon,
  CheckIcon,
  XCircleIcon,
  NoSymbolIcon,
  ArrowUpTrayIcon,
  ArrowRightIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  LightBulbIcon,
  ShieldCheckIcon,
  LinkIcon,
} from '@heroicons/react/24/solid';
import {
  SeverityBadge,
  ConfidenceBadge,
  VerificationBadge,
  SEVERITY_COLORS,
} from '../dashboard/widgets/scanner/ScannerWidgetShared';

/**
 * Code block with line numbers
 */
function CodeBlock({ code, language = 'python', startLine = 1, highlight = false }) {
  const lines = (code || '').split('\n');

  return (
    <div className={`rounded-lg overflow-hidden border ${highlight ? 'border-red-200 dark:border-red-800' : 'border-gray-200 dark:border-gray-700'}`}>
      <pre className="overflow-x-auto text-xs leading-5 bg-gray-50 dark:bg-gray-900/50 p-0">
        <code>
          {lines.map((line, i) => (
            <div
              key={i}
              className={`flex ${highlight ? 'bg-red-50 dark:bg-red-900/10' : ''}`}
            >
              <span className="w-10 flex-shrink-0 text-right pr-3 text-gray-400 select-none border-r border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800/50 py-px">
                {startLine + i}
              </span>
              <span className="pl-3 py-px font-mono whitespace-pre text-gray-800 dark:text-gray-200">
                {line}
              </span>
            </div>
          ))}
        </code>
      </pre>
    </div>
  );
}

/**
 * Diff view (original vs fixed)
 */
function DiffView({ original, fixed }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <p className="text-[10px] font-medium text-red-500 uppercase mb-1.5">Original</p>
        <CodeBlock code={original} highlight />
      </div>
      <div>
        <p className="text-[10px] font-medium text-green-500 uppercase mb-1.5">Fixed</p>
        <div className="rounded-lg overflow-hidden border border-green-200 dark:border-green-800">
          <pre className="overflow-x-auto text-xs leading-5 bg-green-50 dark:bg-green-900/10 p-3">
            <code className="font-mono whitespace-pre text-gray-800 dark:text-gray-200">
              {fixed}
            </code>
          </pre>
        </div>
      </div>
    </div>
  );
}

/**
 * Dataflow chain visualization
 */
function DataflowChain({ dataflow }) {
  if (!dataflow) return null;

  const nodes = [
    { type: 'Source', ...dataflow.source },
    ...(dataflow.propagators || []).map((p) => ({ type: 'Propagator', ...p })),
    { type: 'Sink', ...dataflow.sink },
  ];

  return (
    <div className="space-y-2">
      {nodes.map((node, idx) => (
        <div key={idx}>
          <div className="flex items-start gap-3">
            <div className={`mt-0.5 w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-bold text-white ${
              node.type === 'Source' ? 'bg-blue-500' : node.type === 'Sink' ? 'bg-red-500' : 'bg-gray-400'
            }`}>
              {idx + 1}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className={`text-[10px] font-medium uppercase ${
                  node.type === 'Source' ? 'text-blue-500' : node.type === 'Sink' ? 'text-red-500' : 'text-gray-400'
                }`}>
                  {node.type}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 font-mono">
                  {node.type === 'Source' || node.type === 'Sink' ? node.type : node.type}
                </span>
              </div>
              <p className="text-xs font-mono text-gray-600 dark:text-gray-400 truncate">
                {node.location}
              </p>
              {node.line && (
                <p className="text-[10px] text-gray-400">Line {node.line}</p>
              )}
            </div>
          </div>
          {idx < nodes.length - 1 && (
            <div className="ml-3 border-l-2 border-dashed border-gray-200 dark:border-gray-700 h-3" />
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Section wrapper
 */
function Section({ title, icon: Icon, children }) {
  return (
    <div className="border-t border-gray-200 dark:border-gray-700 pt-5">
      <div className="flex items-center gap-2 mb-3">
        {Icon && <Icon className="w-4 h-4 text-gray-400" />}
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
      </div>
      {children}
    </div>
  );
}

/**
 * FindingDetailDrawer component
 */
export function FindingDetailDrawer({
  finding = null,
  isOpen = false,
  onClose = null,
  onAcceptFix = null,
  onReject = null,
  onFalsePositive = null,
  onEscalate = null,
}) {
  const drawerRef = useRef(null);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) onClose?.();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Trap focus in drawer
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  if (!isOpen || !finding) return null;

  const severityConfig = SEVERITY_COLORS[finding.severity] || SEVERITY_COLORS.INFO;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 transition-opacity duration-300"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className="fixed top-0 right-0 h-full w-full max-w-2xl bg-white dark:bg-surface-800 shadow-2xl z-50 flex flex-col transform transition-transform duration-300 ease-out"
        role="dialog"
        aria-modal="true"
        aria-label={`Finding: ${finding.title}`}
      >
        {/* Header */}
        <div className="flex-shrink-0 p-6 border-b border-gray-200 dark:border-gray-700" style={{ borderLeftWidth: '4px', borderLeftColor: severityConfig.hex }}>
          <div className="flex items-start justify-between">
            <div className="min-w-0 flex-1 mr-4">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-2">
                {finding.title}
              </h2>
              <div className="flex items-center flex-wrap gap-2">
                <SeverityBadge severity={finding.severity} size="md" />
                <ConfidenceBadge confidence={finding.confidence} />
                {finding.cwe_id && (
                  <span className="text-xs px-2 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 font-mono">
                    {finding.cwe_id}
                  </span>
                )}
                {finding.cwe_name && (
                  <span className="text-xs text-gray-500">{finding.cwe_name}</span>
                )}
                <VerificationBadge status={finding.verification_status} />
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Close drawer"
            >
              <XMarkIcon className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Location */}
          <Section title="Location" icon={DocumentTextIcon}>
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono text-blue-600 dark:text-blue-400 hover:underline cursor-pointer">
                {finding.file_path}
              </span>
              <span className="text-xs text-gray-400">
                L{finding.start_line}{finding.end_line ? `-${finding.end_line}` : ''}
              </span>
              <LinkIcon className="w-3.5 h-3.5 text-gray-400" />
            </div>
          </Section>

          {/* Affected Code */}
          {finding.affected_code && (
            <Section title="Affected Code" icon={CodeBracketIcon}>
              <CodeBlock
                code={finding.affected_code}
                startLine={finding.start_line}
                highlight
              />
            </Section>
          )}

          {/* LLM Reasoning */}
          {finding.llm_reasoning && (
            <Section title="LLM Reasoning" icon={LightBulbIcon}>
              <div className="p-3 bg-blue-50 dark:bg-blue-900/10 rounded-lg border border-blue-100 dark:border-blue-800">
                <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                  {finding.llm_reasoning}
                </p>
              </div>
            </Section>
          )}

          {/* Suggested Fix */}
          {finding.suggested_fix && (
            <Section title="Suggested Fix" icon={ShieldCheckIcon}>
              <DiffView
                original={finding.affected_code}
                fixed={finding.suggested_fix}
              />
            </Section>
          )}

          {/* Dataflow Chain */}
          {finding.dataflow && (
            <Section title="Dataflow Chain" icon={ArrowRightIcon}>
              <DataflowChain dataflow={finding.dataflow} />
            </Section>
          )}
        </div>

        {/* Actions Footer */}
        <div className="flex-shrink-0 p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
          <div className="flex items-center gap-2">
            <button
              onClick={() => onAcceptFix?.(finding)}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
            >
              <CheckIcon className="w-4 h-4" />
              Accept Fix
            </button>
            <button
              onClick={() => onReject?.(finding)}
              className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 dark:bg-red-900/20 dark:hover:bg-red-900/30 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-red-500"
            >
              <XCircleIcon className="w-4 h-4" />
              Reject
            </button>
            <button
              onClick={() => onFalsePositive?.(finding)}
              className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-300 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-gray-500"
            >
              <NoSymbolIcon className="w-4 h-4" />
              False Positive
            </button>
            <button
              onClick={() => onEscalate?.(finding)}
              className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-amber-600 bg-amber-50 hover:bg-amber-100 dark:bg-amber-900/20 dark:hover:bg-amber-900/30 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              <ArrowUpTrayIcon className="w-4 h-4" />
              Escalate
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export default FindingDetailDrawer;
