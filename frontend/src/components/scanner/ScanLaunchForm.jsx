/**
 * Scan Launch Form (P0)
 *
 * Form to configure and launch a new vulnerability scan:
 * - Repository URL (required)
 * - Branch (default "main")
 * - Scan Depth with descriptions
 * - Language Filters (multi-select)
 * - Path includes/excludes (tag input)
 * - Autonomy Level
 * - Enable Verification toggle
 * - Max Findings
 * - Estimated cost display
 *
 * Per ADR-084
 *
 * @module components/scanner/ScanLaunchForm
 */

import { useState, useCallback } from 'react';
import {
  PlayCircleIcon,
  XMarkIcon,
  PlusIcon,
  InformationCircleIcon,
  CurrencyDollarIcon,
} from '@heroicons/react/24/solid';
import {
  SCAN_DEPTHS,
  AUTONOMY_LEVELS,
  SUPPORTED_LANGUAGES,
} from '../../services/vulnScannerMockData';

/**
 * Tag input component for path includes/excludes
 */
function TagInput({ label, tags, onAdd, onRemove, placeholder }) {
  const [inputValue, setInputValue] = useState('');

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      e.preventDefault();
      onAdd(inputValue.trim());
      setInputValue('');
    }
    if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
      onRemove(tags.length - 1);
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
        {label}
      </label>
      <div className="flex flex-wrap items-center gap-1.5 p-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/50 min-h-[42px] focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500">
        {tags.map((tag, idx) => (
          <span
            key={idx}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-xs font-mono text-gray-700 dark:text-gray-300"
          >
            {tag}
            <button
              onClick={() => onRemove(idx)}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              aria-label={`Remove ${tag}`}
            >
              <XMarkIcon className="w-3 h-3" />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={tags.length === 0 ? placeholder : ''}
          className="flex-1 min-w-[120px] text-sm bg-transparent border-none outline-none text-gray-900 dark:text-gray-100 placeholder-gray-400"
        />
      </div>
      <p className="mt-1 text-[10px] text-gray-400">Press Enter to add</p>
    </div>
  );
}

/**
 * Multi-select for languages
 */
function LanguageMultiSelect({ selected, onChange }) {
  const [isOpen, setIsOpen] = useState(false);

  const toggleLanguage = (lang) => {
    if (selected.includes(lang)) {
      onChange(selected.filter((l) => l !== lang));
    } else {
      onChange([...selected, lang]);
    }
  };

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
        Language Filters
        <span className="text-xs text-gray-400 ml-1">(optional)</span>
      </label>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full text-left px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/50 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {selected.length > 0 ? (
          <span className="text-gray-900 dark:text-gray-100">
            {selected.length} language{selected.length !== 1 ? 's' : ''} selected
          </span>
        ) : (
          <span className="text-gray-400">All languages (no filter)</span>
        )}
      </button>

      {isOpen && (
        <div className="absolute z-20 mt-1 w-full bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-lg max-h-48 overflow-y-auto">
          {SUPPORTED_LANGUAGES.map((lang) => (
            <label
              key={lang}
              className="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer text-sm"
            >
              <input
                type="checkbox"
                checked={selected.includes(lang)}
                onChange={() => toggleLanguage(lang)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-gray-700 dark:text-gray-300">{lang}</span>
            </label>
          ))}
        </div>
      )}

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {selected.map((lang) => (
            <span key={lang} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-[10px] font-medium text-blue-700 dark:text-blue-300">
              {lang}
              <button onClick={() => toggleLanguage(lang)} className="hover:text-blue-900" aria-label={`Remove ${lang}`}>
                <XMarkIcon className="w-2.5 h-2.5" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * ScanLaunchForm component
 */
export function ScanLaunchForm({
  onSubmit = null,
  onCancel = null,
  className = '',
}) {
  const [formData, setFormData] = useState({
    repository_url: '',
    branch: 'main',
    depth: 'STANDARD',
    languages: [],
    path_includes: [],
    path_excludes: [],
    autonomy_level: 'CRITICAL_HITL',
    enable_verification: true,
    max_findings: 500,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);

  const selectedDepth = SCAN_DEPTHS.find((d) => d.value === formData.depth);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.repository_url.trim()) return;

    setIsSubmitting(true);
    try {
      await onSubmit?.(formData);
    } finally {
      setIsSubmitting(false);
    }
  };

  const updateField = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={`bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="p-6 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">
              Launch New Scan
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Configure and start a vulnerability scan
            </p>
          </div>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Cancel"
            >
              <XMarkIcon className="w-5 h-5 text-gray-500" />
            </button>
          )}
        </div>
      </div>

      {/* Form fields */}
      <div className="p-6 space-y-5">
        {/* Repository URL */}
        <div>
          <label htmlFor="repo-url" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            Repository URL <span className="text-red-500">*</span>
          </label>
          <input
            id="repo-url"
            type="url"
            required
            value={formData.repository_url}
            onChange={(e) => updateField('repository_url', e.target.value)}
            placeholder="https://github.com/org/repo"
            className="w-full px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/50 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Branch */}
        <div>
          <label htmlFor="branch" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            Branch
          </label>
          <input
            id="branch"
            type="text"
            value={formData.branch}
            onChange={(e) => updateField('branch', e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/50 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Scan Depth */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            Scan Depth
          </label>
          <div className="grid grid-cols-2 gap-2">
            {SCAN_DEPTHS.map((depth) => (
              <button
                key={depth.value}
                type="button"
                onClick={() => updateField('depth', depth.value)}
                className={`text-left p-3 rounded-lg border-2 transition-all ${
                  formData.depth === depth.value
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                }`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className={`text-sm font-medium ${
                    formData.depth === depth.value ? 'text-blue-700 dark:text-blue-300' : 'text-gray-900 dark:text-gray-100'
                  }`}>
                    {depth.label}
                  </span>
                  <span className="text-xs text-gray-400">{depth.estimatedCost}</span>
                </div>
                <p className="text-[11px] text-gray-500">{depth.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Language Filters */}
        <LanguageMultiSelect
          selected={formData.languages}
          onChange={(langs) => updateField('languages', langs)}
        />

        {/* Path Includes */}
        <TagInput
          label="Path Includes"
          tags={formData.path_includes}
          onAdd={(tag) => updateField('path_includes', [...formData.path_includes, tag])}
          onRemove={(idx) => updateField('path_includes', formData.path_includes.filter((_, i) => i !== idx))}
          placeholder="src/api/** (glob patterns)"
        />

        {/* Path Excludes */}
        <TagInput
          label="Path Excludes"
          tags={formData.path_excludes}
          onAdd={(tag) => updateField('path_excludes', [...formData.path_excludes, tag])}
          onRemove={(idx) => updateField('path_excludes', formData.path_excludes.filter((_, i) => i !== idx))}
          placeholder="**/test/** (glob patterns)"
        />

        {/* Autonomy Level */}
        <div>
          <label htmlFor="autonomy" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            Autonomy Level
          </label>
          <select
            id="autonomy"
            value={formData.autonomy_level}
            onChange={(e) => updateField('autonomy_level', e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/50 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {AUTONOMY_LEVELS.map((level) => (
              <option key={level.value} value={level.value}>
                {level.label} - {level.description}
              </option>
            ))}
          </select>
        </div>

        {/* Two-column: Verification + Max Findings */}
        <div className="grid grid-cols-2 gap-4">
          {/* Enable Verification */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Enable Verification
            </label>
            <button
              type="button"
              role="switch"
              aria-checked={formData.enable_verification}
              onClick={() => updateField('enable_verification', !formData.enable_verification)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                formData.enable_verification ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                formData.enable_verification ? 'translate-x-6' : 'translate-x-1'
              }`} />
            </button>
            <p className="text-[10px] text-gray-400 mt-1">
              Run automated verification on findings
            </p>
          </div>

          {/* Max Findings */}
          <div>
            <label htmlFor="max-findings" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Max Findings
            </label>
            <input
              id="max-findings"
              type="number"
              min="1"
              max="10000"
              value={formData.max_findings}
              onChange={(e) => updateField('max_findings', parseInt(e.target.value, 10) || 500)}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/50 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Footer with cost estimate and actions */}
      <div className="p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
        {/* Estimated cost */}
        <div className="flex items-center gap-2 mb-4 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-800">
          <CurrencyDollarIcon className="w-5 h-5 text-blue-500 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-blue-700 dark:text-blue-300">
              Estimated cost: {selectedDepth?.estimatedCost || '$0.85'}
            </p>
            <p className="text-[10px] text-blue-500">
              Based on {selectedDepth?.label || 'Standard'} depth. Actual cost depends on repository size.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={isSubmitting || !formData.repository_url.trim()}
            className="flex items-center gap-2 px-6 py-2.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            <PlayCircleIcon className="w-4 h-4" />
            {isSubmitting ? 'Launching...' : 'Launch Scan'}
          </button>
        </div>
      </div>
    </form>
  );
}

export default ScanLaunchForm;
