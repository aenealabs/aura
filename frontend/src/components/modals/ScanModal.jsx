/**
 * Project Aura - Security Scan Modal Component
 *
 * Modal for initiating security scans with configurable options.
 * Supports full repository scans, quick vulnerability checks, and targeted scans.
 *
 * Design System: Apple-inspired with clean typography, generous spacing,
 * and smooth transitions per design-principles.md
 */

import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import {
  XMarkIcon,
  PlayIcon,
  MagnifyingGlassIcon,
  ShieldCheckIcon,
  BugAntIcon,
  CodeBracketIcon,
  FolderIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { listRepositories } from '../../services/repositoryApi';

// Scan type configurations
const SCAN_TYPES = [
  {
    id: 'full',
    name: 'Full Security Scan',
    description: 'Comprehensive vulnerability analysis including SAST, dependency audit, and secret detection',
    icon: ShieldCheckIcon,
    estimatedTime: '5-15 minutes',
    color: 'aura',
    features: ['OWASP Top 10', 'CVE Detection', 'Secrets Scanning', 'Dependency Audit'],
  },
  {
    id: 'quick',
    name: 'Quick Vulnerability Check',
    description: 'Fast scan focusing on critical and high severity vulnerabilities',
    icon: BugAntIcon,
    estimatedTime: '1-3 minutes',
    color: 'olive',
    features: ['Critical CVEs', 'High-Risk Patterns', 'Known Exploits'],
  },
  {
    id: 'targeted',
    name: 'Targeted Analysis',
    description: 'Scan specific files or directories for security issues',
    icon: MagnifyingGlassIcon,
    estimatedTime: '30 seconds - 2 minutes',
    color: 'warning',
    features: ['File-Level Scan', 'Custom Patterns', 'Quick Results'],
  },
];

// Color mappings for design system
const COLOR_STYLES = {
  aura: {
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    border: 'border-aura-200 dark:border-aura-700',
    text: 'text-aura-600 dark:text-aura-400',
    icon: 'bg-aura-100 dark:bg-aura-900/30 text-aura-600 dark:text-aura-400',
    selected: 'ring-2 ring-aura-500 border-aura-500',
  },
  olive: {
    bg: 'bg-olive-50 dark:bg-olive-900/20',
    border: 'border-olive-200 dark:border-olive-700',
    text: 'text-olive-600 dark:text-olive-400',
    icon: 'bg-olive-100 dark:bg-olive-900/30 text-olive-600 dark:text-olive-400',
    selected: 'ring-2 ring-aura-500 border-aura-500',
  },
  warning: {
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    border: 'border-warning-200 dark:border-warning-700',
    text: 'text-warning-600 dark:text-warning-400',
    icon: 'bg-warning-100 dark:bg-warning-900/30 text-warning-600 dark:text-warning-400',
    selected: 'ring-2 ring-aura-500 border-aura-500',
  },
};

/**
 * Format a date for display in the repository list
 */
function formatLastScan(dateStr) {
  if (!dateStr) return 'Never';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  return date.toLocaleDateString();
}

/**
 * Scan Type Card Component
 */
function ScanTypeCard({ scanType, isSelected, onSelect }) {
  const colors = COLOR_STYLES[scanType.color] || COLOR_STYLES.aura;
  const Icon = scanType.icon;

  return (
    <button
      onClick={() => onSelect(scanType.id)}
      className={`
        w-full text-left p-4 rounded-xl border transition-all duration-200 ease-[var(--ease-tahoe)]
        ${isSelected
          ? `${colors.bg} backdrop-blur-sm ${colors.selected} shadow-[var(--shadow-glass-hover)]`
          : 'border-surface-200/50 dark:border-surface-700/30 bg-white dark:bg-surface-800 backdrop-blur-xl hover:border-surface-300/60 dark:hover:border-surface-600/40 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)]'
        }
      `}
    >
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg ${colors.icon}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">
            {scanType.name}
          </h3>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
            {scanType.description}
          </p>
          <div className="flex items-center gap-1 mt-2 text-xs text-surface-500 dark:text-surface-400">
            <ClockIcon className="w-3.5 h-3.5" />
            {scanType.estimatedTime}
          </div>
          <div className="flex flex-wrap gap-1.5 mt-3">
            {scanType.features.map((feature, idx) => (
              <span
                key={idx}
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300"
              >
                {feature}
              </span>
            ))}
          </div>
        </div>
      </div>
    </button>
  );
}

/**
 * Repository Selector Component
 */
function RepositorySelector({ repositories, selectedRepo, onSelect, loading }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedRepository = repositories.find((r) => r.id === selectedRepo);

  return (
    <div className="relative" ref={dropdownRef}>
      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
        Target Repository
      </label>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading}
        className={`
          w-full flex items-center justify-between px-4 py-3 rounded-xl border
          bg-white dark:bg-surface-800 backdrop-blur-sm border-surface-200/50 dark:border-surface-600/50
          text-surface-900 dark:text-surface-100
          hover:border-surface-300/60 dark:hover:border-surface-500/50 hover:bg-white/80 dark:hover:bg-surface-700
          focus:outline-none focus:ring-2 focus:ring-aura-500 focus:border-aura-500
          transition-all duration-200 ease-[var(--ease-tahoe)]
          disabled:opacity-50 disabled:cursor-not-allowed
        `}
      >
        {selectedRepository ? (
          <div className="flex items-center gap-2">
            <FolderIcon className="w-5 h-5 text-surface-400" />
            <span className="font-medium">{selectedRepository.name}</span>
            <span className="text-sm text-surface-500 dark:text-surface-400">
              ({selectedRepository.branch})
            </span>
          </div>
        ) : (
          <span className="text-surface-400">Select a repository...</span>
        )}
        <ChevronDownIcon className={`w-5 h-5 text-surface-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-10 w-full mt-2 bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 border border-surface-200/50 dark:border-surface-700/30 rounded-xl shadow-[var(--shadow-glass-hover)] overflow-hidden">
          <div className="max-h-64 overflow-y-auto">
            {repositories.map((repo) => (
              <button
                key={repo.id}
                onClick={() => {
                  onSelect(repo.id);
                  setIsOpen(false);
                }}
                className={`
                  w-full flex items-center justify-between px-4 py-3 text-left
                  hover:bg-white/60 dark:hover:bg-surface-700
                  transition-all duration-200 ease-[var(--ease-tahoe)]
                  ${selectedRepo === repo.id ? 'bg-aura-50/80 dark:bg-aura-900/20' : ''}
                `}
              >
                <div className="flex items-center gap-3">
                  <FolderIcon className="w-5 h-5 text-surface-400" />
                  <div>
                    <p className="font-medium text-surface-900 dark:text-surface-100">
                      {repo.name}
                    </p>
                    <p className="text-xs text-surface-500 dark:text-surface-400">
                      {repo.provider} / {repo.branch}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-surface-500 dark:text-surface-400">
                    Last scan: {repo.lastScan}
                  </p>
                  {selectedRepo === repo.id && (
                    <CheckCircleIcon className="w-5 h-5 text-aura-500 mt-1 ml-auto" />
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Main Scan Modal Component
 */
export default function ScanModal({ isOpen, onClose, onScanStart }) {
  const [scanType, setScanType] = useState('full');
  const [selectedRepo, setSelectedRepo] = useState('');
  const [targetPath, setTargetPath] = useState('');
  const [repositories, setRepositories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const modalRef = useRef(null);

  // Load repositories on mount
  useEffect(() => {
    if (isOpen) {
      loadRepositories();
    }
  }, [isOpen]);

  // Handle escape key and focus trap
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !submitting) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, submitting, onClose]);

  const loadRepositories = async () => {
    setLoading(true);
    setError(null);
    try {
      const repos = await listRepositories();
      // Transform API response to match component expectations
      const formattedRepos = (repos || []).map((repo) => ({
        id: repo.repository_id,
        name: repo.name,
        provider: repo.provider || 'github',
        branch: repo.branch || 'main',
        lastScan: formatLastScan(repo.last_scan),
      }));
      setRepositories(formattedRepos);
    } catch (err) {
      setError('Failed to load repositories. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleStartScan = async () => {
    if (!selectedRepo) {
      setError('Please select a repository to scan.');
      return;
    }

    if (scanType === 'targeted' && !targetPath.trim()) {
      setError('Please specify a target path for targeted analysis.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      // Build scan configuration
      const scanConfig = {
        type: scanType,
        repositoryId: selectedRepo,
        targetPath: scanType === 'targeted' ? targetPath : undefined,
        startedAt: new Date().toISOString(),
      };

      // In production, this would call the scan API
      // await startSecurityScan(scanConfig);
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Notify parent and close
      onScanStart?.(scanConfig);
      onClose();
    } catch (err) {
      setError('Failed to start scan. Please try again.');
      console.error('Failed to start scan:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const selectedScanType = SCAN_TYPES.find((t) => t.id === scanType);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="scan-modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-md transition-opacity duration-200"
        onClick={submitting ? undefined : onClose}
      />

      {/* Modal */}
      <div
        ref={modalRef}
        className="relative bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-2xl shadow-[var(--shadow-glass-hover)] max-w-2xl w-full max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-aura-100 dark:bg-aura-900/30">
                <PlayIcon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
              </div>
              <div>
                <h2
                  id="scan-modal-title"
                  className="text-lg font-semibold text-surface-900 dark:text-surface-100"
                >
                  Start Security Scan
                </h2>
                <p className="text-sm text-surface-500 dark:text-surface-400">
                  Configure and initiate a security analysis
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              disabled={submitting}
              className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-200 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
              aria-label="Close modal"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">
          {/* Error Banner */}
          {error && (
            <div className="mb-6 p-4 rounded-xl bg-critical-50/90 dark:bg-critical-900/20 backdrop-blur-sm border border-critical-200/50 dark:border-critical-800/50 flex items-start gap-3 shadow-[var(--shadow-glass)]">
              <ExclamationTriangleIcon className="w-5 h-5 text-critical-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-critical-800 dark:text-critical-300">{error}</p>
              </div>
            </div>
          )}

          {/* Scan Type Selection */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-3">
              Scan Type
            </h3>
            <div className="space-y-3">
              {SCAN_TYPES.map((type) => (
                <ScanTypeCard
                  key={type.id}
                  scanType={type}
                  isSelected={scanType === type.id}
                  onSelect={setScanType}
                />
              ))}
            </div>
          </div>

          {/* Repository Selection */}
          <div className="mb-6">
            <RepositorySelector
              repositories={repositories}
              selectedRepo={selectedRepo}
              onSelect={setSelectedRepo}
              loading={loading}
            />
            {loading && (
              <div className="flex items-center gap-2 mt-2 text-sm text-surface-500 dark:text-surface-400">
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
                Loading repositories...
              </div>
            )}
          </div>

          {/* Target Path (for targeted scans) */}
          {scanType === 'targeted' && (
            <div className="mb-6">
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                Target Path
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400">
                  <CodeBracketIcon className="w-5 h-5" />
                </div>
                <input
                  type="text"
                  value={targetPath}
                  onChange={(e) => setTargetPath(e.target.value)}
                  placeholder="e.g., src/auth/, controllers/UserController.java"
                  className="w-full pl-10 pr-4 py-3 rounded-xl border border-surface-200/50 dark:border-surface-600/50 bg-white dark:bg-surface-800 backdrop-blur-sm text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 transition-all duration-200 ease-[var(--ease-tahoe)]"
                />
              </div>
              <p className="mt-2 text-xs text-surface-500 dark:text-surface-400">
                Specify files or directories to scan. Supports glob patterns.
              </p>
            </div>
          )}

          {/* Scan Summary */}
          {selectedRepo && selectedScanType && (
            <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800 backdrop-blur-sm border border-surface-200/30 dark:border-surface-600/20">
              <div className="flex items-start gap-3">
                <InformationCircleIcon className="w-5 h-5 text-aura-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm">
                  <p className="font-medium text-surface-900 dark:text-surface-100">Scan Summary</p>
                  <ul className="mt-2 space-y-1 text-surface-600 dark:text-surface-400">
                    <li>Type: {selectedScanType.name}</li>
                    <li>Repository: {repositories.find((r) => r.id === selectedRepo)?.name}</li>
                    <li>Estimated time: {selectedScanType.estimatedTime}</li>
                    {scanType === 'targeted' && targetPath && (
                      <li>Target: {targetPath}</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-100/50 dark:border-surface-700/30 bg-white/60 dark:bg-surface-800/50 backdrop-blur-sm flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2.5 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleStartScan}
            disabled={submitting || !selectedRepo || loading}
            className="px-6 py-2.5 text-sm font-medium bg-aura-600 text-white rounded-xl hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)] flex items-center gap-2 shadow-sm hover:shadow-md"
          >
            {submitting ? (
              <>
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <PlayIcon className="w-4 h-4" />
                Start Scan
              </>
            )}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
