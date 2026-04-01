/**
 * Project Aura - Action Modify Modal Component
 *
 * Modal for editing action parameters before execution.
 * Features:
 * - JSON parameter editing with syntax highlighting
 * - Before/after comparison view
 * - Parameter validation
 * - Trust scope selection
 *
 * @see Design Principles: Apple-inspired modal patterns
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  DocumentDuplicateIcon,
  ArrowsRightLeftIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';

import { useExecution } from '../../context/ExecutionContext';

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Validate JSON string
 */
function validateJson(jsonString) {
  try {
    JSON.parse(jsonString);
    return { valid: true, error: null };
  } catch (e) {
    return { valid: false, error: e.message };
  }
}

/**
 * Deep compare two objects
 */
function deepEqual(obj1, obj2) {
  return JSON.stringify(obj1) === JSON.stringify(obj2);
}

/**
 * Get diff between two objects
 */
function getDiff(original, modified) {
  const changes = [];
  const allKeys = new Set([...Object.keys(original || {}), ...Object.keys(modified || {})]);

  allKeys.forEach((key) => {
    const originalValue = original?.[key];
    const modifiedValue = modified?.[key];

    if (originalValue !== modifiedValue) {
      changes.push({
        key,
        original: originalValue,
        modified: modifiedValue,
        type: originalValue === undefined ? 'added' : modifiedValue === undefined ? 'removed' : 'changed',
      });
    }
  });

  return changes;
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

/**
 * Trust Scope Selector
 */
function TrustScopeSelector({ value, onChange }) {
  const { TrustScope } = useExecution();

  const options = [
    {
      value: TrustScope.THIS_ACTION,
      label: 'This action only',
      description: 'Apply modification to this specific action',
    },
    {
      value: TrustScope.THIS_ACTION_TYPE,
      label: 'This action type',
      description: 'Auto-approve similar modifications this session',
    },
    {
      value: TrustScope.THIS_SESSION,
      label: 'All similar actions',
      description: 'Trust all similar actions for this session',
    },
  ];

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
        Trust Scope
      </label>
      <div className="space-y-2">
        {options.map((option) => (
          <label
            key={option.value}
            className={`
              flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all duration-200 ease-[var(--ease-tahoe)]
              ${value === option.value
                ? 'border-aura-500 bg-aura-100/80 dark:bg-aura-900/30 backdrop-blur-sm shadow-[var(--shadow-glass)]'
                : 'border-surface-200/50 dark:border-surface-700/30 bg-surface-50 dark:bg-surface-800 hover:bg-white/80 dark:hover:bg-surface-700 hover:border-surface-300/60 dark:hover:border-surface-600/40'
              }
            `}
          >
            <input
              type="radio"
              name="trustScope"
              value={option.value}
              checked={value === option.value}
              onChange={(e) => onChange(e.target.value)}
              className="mt-0.5 w-4 h-4 text-aura-500 border-surface-300 focus:ring-aura-500 dark:border-surface-600"
            />
            <div>
              <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                {option.label}
              </span>
              <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                {option.description}
              </p>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}

/**
 * Changes Preview
 */
function ChangesPreview({ original, modified }) {
  const changes = useMemo(() => getDiff(original, modified), [original, modified]);

  if (changes.length === 0) {
    return (
      <div className="p-4 text-center text-surface-500 dark:text-surface-400 text-sm">
        No changes detected
      </div>
    );
  }

  return (
    <div className="divide-y divide-surface-200 dark:divide-surface-700">
      {changes.map((change) => (
        <div key={change.key} className="p-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium text-surface-900 dark:text-surface-100 font-mono">
              {change.key}
            </span>
            <span className={`
              px-1.5 py-0.5 rounded text-xs font-medium
              ${change.type === 'added'
                ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400'
                : change.type === 'removed'
                  ? 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400'
                  : 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400'
              }
            `}>
              {change.type}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4 text-xs font-mono">
            <div className={`p-2 rounded ${change.type === 'added' ? 'bg-surface-100 dark:bg-surface-800' : 'bg-critical-50 dark:bg-critical-900/10'}`}>
              <span className="text-surface-500 dark:text-surface-400 text-[10px] uppercase block mb-1">
                Original
              </span>
              <span className={change.type === 'added' ? 'text-surface-400' : 'text-critical-600 dark:text-critical-400'}>
                {change.original === undefined ? 'undefined' : JSON.stringify(change.original)}
              </span>
            </div>
            <div className={`p-2 rounded ${change.type === 'removed' ? 'bg-surface-100 dark:bg-surface-800' : 'bg-olive-50 dark:bg-olive-900/10'}`}>
              <span className="text-surface-500 dark:text-surface-400 text-[10px] uppercase block mb-1">
                Modified
              </span>
              <span className={change.type === 'removed' ? 'text-surface-400' : 'text-olive-600 dark:text-olive-400'}>
                {change.modified === undefined ? 'undefined' : JSON.stringify(change.modified)}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

/**
 * Action Modify Modal
 */
export default function ActionModifyModal() {
  const {
    modifyModalOpen,
    modifyingAction,
    closeModifyModal,
    modifyAction,
    loading,
    TrustScope,
    ACTION_TYPE_CONFIG,
  } = useExecution();

  // Local state
  const [parametersText, setParametersText] = useState('');
  const [parsedParameters, setParsedParameters] = useState(null);
  const [validationError, setValidationError] = useState(null);
  const [trustScope, setTrustScope] = useState(TrustScope.THIS_ACTION);
  const [showComparison, setShowComparison] = useState(false);

  // Initialize parameters when action changes
  useEffect(() => {
    if (modifyingAction?.parameters) {
      const text = JSON.stringify(modifyingAction.parameters, null, 2);
      setParametersText(text);
      setParsedParameters(modifyingAction.parameters);
      setValidationError(null);
      setTrustScope(TrustScope.THIS_ACTION);
      setShowComparison(false);
    }
  }, [modifyingAction, TrustScope]);

  // Validate and parse parameters on change
  useEffect(() => {
    const result = validateJson(parametersText);
    if (result.valid) {
      setParsedParameters(JSON.parse(parametersText));
      setValidationError(null);
    } else {
      setValidationError(result.error);
    }
  }, [parametersText]);

  // Check if there are changes
  const hasChanges = useMemo(() => {
    if (!modifyingAction?.parameters || !parsedParameters) return false;
    return !deepEqual(modifyingAction.parameters, parsedParameters);
  }, [modifyingAction?.parameters, parsedParameters]);

  // Handle submit
  const handleSubmit = useCallback(async () => {
    if (!modifyingAction || !parsedParameters || validationError) return;

    try {
      await modifyAction(modifyingAction.action_id, parsedParameters, trustScope);
    } catch (err) {
      console.error('Failed to modify action:', err);
    }
  }, [modifyingAction, parsedParameters, trustScope, validationError, modifyAction]);

  // Handle copy to clipboard
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(parametersText);
  }, [parametersText]);

  // Handle reset
  const handleReset = useCallback(() => {
    if (modifyingAction?.parameters) {
      setParametersText(JSON.stringify(modifyingAction.parameters, null, 2));
    }
  }, [modifyingAction]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && modifyModalOpen) {
        closeModifyModal();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [modifyModalOpen, closeModifyModal]);

  // Don't render if not open
  if (!modifyModalOpen || !modifyingAction) return null;

  const typeConfig = ACTION_TYPE_CONFIG[modifyingAction.type] || { label: modifyingAction.type };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-md transition-opacity"
        onClick={closeModifyModal}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          className="relative w-full max-w-2xl bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-2xl shadow-[var(--shadow-glass-hover)] overflow-hidden animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30 flex items-center justify-between">
            <div>
              <h2
                id="modal-title"
                className="text-lg font-semibold text-surface-900 dark:text-surface-100"
              >
                Modify {typeConfig.label}
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5 font-mono truncate max-w-md">
                {modifyingAction.target}
              </p>
            </div>
            <button
              onClick={closeModifyModal}
              className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
              aria-label="Close modal"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="p-6 max-h-[60vh] overflow-y-auto">
            {/* Editor */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
                  Parameters (JSON)
                </label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopy}
                    className="p-1.5 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded transition-colors"
                    title="Copy to clipboard"
                  >
                    <DocumentDuplicateIcon className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleReset}
                    disabled={!hasChanges}
                    className="p-1.5 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Reset to original"
                  >
                    <ArrowPathIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="relative">
                <textarea
                  value={parametersText}
                  onChange={(e) => setParametersText(e.target.value)}
                  rows={12}
                  className={`
                    w-full px-4 py-3 font-mono text-sm rounded-xl border
                    bg-white dark:bg-surface-800 backdrop-blur-sm text-surface-900 dark:text-surface-100
                    placeholder-surface-400 resize-none transition-all duration-200 ease-[var(--ease-tahoe)]
                    focus:ring-2 focus:ring-aura-500 focus:border-transparent
                    ${validationError
                      ? 'border-critical-300/70 dark:border-critical-700/70'
                      : 'border-surface-200/50 dark:border-surface-600/50'
                    }
                  `}
                  placeholder="Enter JSON parameters..."
                  spellCheck={false}
                />

                {/* Validation error */}
                {validationError && (
                  <div className="absolute bottom-0 left-0 right-0 px-3 py-2 bg-critical-50/90 dark:bg-critical-900/30 backdrop-blur-sm border-t border-critical-200/50 dark:border-critical-800/50 rounded-b-xl">
                    <div className="flex items-center gap-2 text-critical-700 dark:text-critical-400 text-xs">
                      <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0" />
                      <span className="truncate">{validationError}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Comparison toggle */}
            {hasChanges && (
              <button
                onClick={() => setShowComparison(!showComparison)}
                className="flex items-center gap-2 text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 mb-4"
              >
                <ArrowsRightLeftIcon className="w-4 h-4" />
                {showComparison ? 'Hide comparison' : 'Show comparison'}
              </button>
            )}

            {/* Changes Preview */}
            {showComparison && hasChanges && (
              <div className="mb-6 border border-surface-200/50 dark:border-surface-700/30 rounded-xl overflow-hidden shadow-[var(--shadow-glass)]">
                <div className="px-4 py-2 bg-surface-50 dark:bg-surface-800 backdrop-blur-sm border-b border-surface-200/30 dark:border-surface-700/20">
                  <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
                    Changes Preview
                  </span>
                </div>
                <ChangesPreview
                  original={modifyingAction.parameters}
                  modified={parsedParameters}
                />
              </div>
            )}

            {/* Trust Scope */}
            <TrustScopeSelector
              value={trustScope}
              onChange={setTrustScope}
            />
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-surface-100/50 dark:border-surface-700/30 bg-white/60 dark:bg-surface-800/50 backdrop-blur-sm flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-surface-500 dark:text-surface-400">
              <ShieldCheckIcon className="w-4 h-4" />
              <span>Modifications are logged for audit</span>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={closeModifyModal}
                className="px-4 py-2.5 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!hasChanges || !!validationError || loading.modify}
                className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-aura-500 rounded-xl hover:bg-aura-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)] shadow-sm hover:shadow-md"
              >
                {loading.modify ? (
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                ) : (
                  <CheckIcon className="w-4 h-4" />
                )}
                Apply and Approve
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
