/**
 * Project Aura - Repositories List Page
 *
 * Main page displaying connected repositories with management actions.
 * Includes search, filter, and quick actions for each repository.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

import { useState, useMemo, useEffect, useCallback } from 'react';
import { ArrowPathIcon, XMarkIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { useRepositories } from '../../context/RepositoryContext';
import { RepositoryStatus, updateRepository, ScanFrequency } from '../../services/repositoryApi';
import RepositoryOnboardWizard from './RepositoryOnboardWizard';
import RepositoryCard from './RepositoryCard';
import { PageSkeleton } from '../ui/LoadingSkeleton';
import { useToast } from '../ui/Toast';
import { useConfirm } from '../ui/ConfirmDialog';

const RepositoriesList = () => {
  const {
    repositories,
    connections,
    isLoadingRepositories,
    error,
    loadRepositories,
    openWizard: _openWizard,
    isWizardOpen: _isWizardOpen,
    deleteRepository,
    triggerSync,
  } = useRepositories();

  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterProvider, setFilterProvider] = useState('all');
  const [viewMode, setViewMode] = useState('grid'); // grid or list
  const [showWizard, setShowWizard] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [editingRepository, setEditingRepository] = useState(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const { toast } = useToast();
  const { confirm } = useConfirm();

  // Filter and search repositories
  const filteredRepositories = useMemo(() => {
    let repos = [...repositories];

    // Search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      repos = repos.filter(
        (repo) =>
          repo.name.toLowerCase().includes(term) ||
          repo.clone_url.toLowerCase().includes(term)
      );
    }

    // Status filter
    if (filterStatus !== 'all') {
      repos = repos.filter((repo) => repo.status === filterStatus);
    }

    // Provider filter
    if (filterProvider !== 'all') {
      repos = repos.filter((repo) => repo.provider === filterProvider);
    }

    return repos;
  }, [repositories, searchTerm, filterStatus, filterProvider]);

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await loadRepositories();
      toast.success('Repositories refreshed');
    } catch (err) {
      toast.error('Failed to refresh repositories');
    } finally {
      setIsRefreshing(false);
    }
  }, [loadRepositories, toast]);

  // Track initial load completion
  useEffect(() => {
    if (!isLoadingRepositories && isInitialLoad) {
      const timer = setTimeout(() => setIsInitialLoad(false), 300);
      return () => clearTimeout(timer);
    }
  }, [isLoadingRepositories, isInitialLoad]);

  // Show page skeleton on initial load
  if (isInitialLoad && isLoadingRepositories) {
    return <PageSkeleton />;
  }

  const handleAddRepository = () => {
    setShowWizard(true);
  };

  const handleWizardComplete = () => {
    setShowWizard(false);
    loadRepositories();
  };

  const handleWizardCancel = () => {
    setShowWizard(false);
  };

  const handleDelete = async (repositoryId) => {
    const confirmed = await confirm({
      title: 'Remove Repository',
      message: 'Are you sure you want to remove this repository? This will delete all indexed data.',
      confirmText: 'Remove',
      cancelText: 'Cancel',
      variant: 'danger',
    });
    if (confirmed) {
      await deleteRepository(repositoryId);
    }
  };

  const handleSync = async (repositoryId) => {
    await triggerSync(repositoryId);
  };

  const handleEdit = (repository) => {
    setEditingRepository({
      ...repository,
      // Ensure we have editable fields with defaults
      branch: repository.branch || 'main',
      scanFrequency: repository.scan_frequency || ScanFrequency.ON_PUSH,
      excludePatterns: repository.exclude_patterns || [],
    });
  };

  const handleSaveEdit = async () => {
    if (!editingRepository) return;

    setIsSavingEdit(true);
    try {
      await updateRepository(editingRepository.repository_id, {
        name: editingRepository.name,
        branch: editingRepository.branch,
        scanFrequency: editingRepository.scanFrequency,
        excludePatterns: editingRepository.excludePatterns,
      });
      toast.success('Repository settings updated');
      setEditingRepository(null);
      loadRepositories();
    } catch (err) {
      toast.error('Failed to update repository settings');
    } finally {
      setIsSavingEdit(false);
    }
  };

  const _formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700 px-6 py-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 max-w-7xl mx-auto">
          <div>
            <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              Repositories
            </h1>
            <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
              Manage your connected code repositories for analysis.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-3 py-2 text-sm text-surface-600 dark:text-surface-400
                hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-50 dark:hover:bg-surface-700
                rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)]"
              aria-label="Refresh repositories"
            >
              <ArrowPathIcon className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
            <button
              onClick={handleAddRepository}
              className="inline-flex items-center px-4 py-2 bg-aura-600 text-white rounded-xl hover:bg-aura-700 hover:-translate-y-px hover:shadow-md active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-aura-500 transition-all duration-200 ease-[var(--ease-tahoe)]"
            >
              <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Repository
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
            <input
              type="text"
              placeholder="Search repositories..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>
        </div>
        <div className="flex gap-2">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
          >
            <option value="all">All Status</option>
            <option value={RepositoryStatus.ACTIVE}>Active</option>
            <option value={RepositoryStatus.SYNCING}>Syncing</option>
            <option value={RepositoryStatus.ERROR}>Error</option>
            <option value={RepositoryStatus.PENDING}>Pending</option>
          </select>
          <select
            value={filterProvider}
            onChange={(e) => setFilterProvider(e.target.value)}
            className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
          >
            <option value="all">All Providers</option>
            <option value="github">GitHub</option>
            <option value="gitlab">GitLab</option>
            <option value="manual">Manual</option>
          </select>
          <div className="flex border border-surface-300 dark:border-surface-600 rounded-lg overflow-hidden" role="group" aria-label="View mode">
            <button
              onClick={() => setViewMode('grid')}
              aria-label="Grid view"
              aria-pressed={viewMode === 'grid'}
              className={`p-2 transition-all duration-200 ease-[var(--ease-tahoe)] ${
                viewMode === 'grid'
                  ? 'bg-aura-50/80 dark:bg-aura-900/30 text-aura-600'
                  : 'bg-white dark:bg-surface-800 text-surface-500 hover:bg-surface-50 dark:hover:bg-surface-700'
              }`}
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('list')}
              aria-label="List view"
              aria-pressed={viewMode === 'list'}
              className={`p-2 transition-all duration-200 ease-[var(--ease-tahoe)] ${
                viewMode === 'list'
                  ? 'bg-aura-50/80 dark:bg-aura-900/30 text-aura-600'
                  : 'bg-white dark:bg-surface-800 text-surface-500 hover:bg-surface-50 dark:hover:bg-surface-700'
              }`}
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-critical-50/80 dark:bg-critical-900/20 backdrop-blur-sm border border-critical-200/50 dark:border-critical-800/50 rounded-xl">
          <p className="text-sm text-critical-700 dark:text-critical-400">{error}</p>
        </div>
      )}

      {/* Loading State */}
      {isLoadingRepositories ? (
        <div className="flex items-center justify-center py-12">
          <svg className="animate-spin h-8 w-8 text-aura-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        </div>
      ) : filteredRepositories.length === 0 ? (
        /* Empty State */
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-surface-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1}
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-surface-900 dark:text-surface-100">
            {searchTerm || filterStatus !== 'all' || filterProvider !== 'all'
              ? 'No repositories match your filters'
              : 'No repositories connected'}
          </h3>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
            {searchTerm || filterStatus !== 'all' || filterProvider !== 'all'
              ? 'Try adjusting your search or filters.'
              : 'Get started by adding your first repository.'}
          </p>
          {!searchTerm && filterStatus === 'all' && filterProvider === 'all' && (
            <div className="mt-6">
              <button
                onClick={handleAddRepository}
                className="inline-flex items-center px-4 py-2 bg-aura-600 text-white rounded-xl hover:bg-aura-700 hover:-translate-y-px hover:shadow-md active:scale-[0.98] transition-all duration-200 ease-[var(--ease-tahoe)]"
              >
                <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add Repository
              </button>
            </div>
          )}
        </div>
      ) : (
        /* Repository Grid/List */
        <div
          className={
            viewMode === 'grid'
              ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'
              : 'space-y-3'
          }
        >
          {filteredRepositories.map((repo) => (
            <RepositoryCard
              key={repo.repository_id}
              repository={repo}
              viewMode={viewMode}
              onEdit={() => handleEdit(repo)}
              onDelete={() => handleDelete(repo.repository_id)}
              onSync={() => handleSync(repo.repository_id)}
            />
          ))}
        </div>
      )}

      {/* Connections Summary */}
      {connections.length > 0 && (
        <div className="mt-8 pt-8 border-t border-surface-200/50 dark:border-surface-700/30">
          <h2 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-4">
            Connected Accounts
          </h2>
          <div className="flex flex-wrap gap-2">
            {connections.map((conn) => (
              <div
                key={conn.connection_id}
                className="inline-flex items-center px-3 py-1.5 bg-white dark:bg-surface-800 backdrop-blur-sm border border-surface-200/50 dark:border-surface-700/30 rounded-full text-sm"
              >
                {conn.provider === 'github' && (
                  <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                  </svg>
                )}
                {conn.provider === 'gitlab' && (
                  <svg className="w-4 h-4 mr-2 text-warning-600" viewBox="0 0 24 24" fill="currentColor">
                    <path d="m23.546 10.93-1.73-5.326-3.401-10.47a.483.483 0 0 0-.919 0l-3.402 10.47H9.908L6.506-5.134a.483.483 0 0 0-.919 0L2.185 5.604.455 10.93a.93.93 0 0 0 .338 1.04L12 19.87l11.207-7.9a.93.93 0 0 0 .339-1.04z" />
                  </svg>
                )}
                <span className="text-surface-700 dark:text-surface-300">
                  @{conn.provider_username}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Wizard Modal */}
      {showWizard && (
        <RepositoryOnboardWizard
          onComplete={handleWizardComplete}
          onCancel={handleWizardCancel}
        />
      )}

      {/* Edit Repository Modal */}
      {editingRepository && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 glass-backdrop"
            onClick={() => !isSavingEdit && setEditingRepository(null)}
          />
          <div className="
            relative max-w-lg w-full p-6
            bg-white/95 dark:bg-surface-800/95
            backdrop-blur-xl backdrop-saturate-150
            rounded-2xl
            border border-white/50 dark:border-surface-700/50
            shadow-[var(--shadow-glass-hover)]
            animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]
          ">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                Edit Repository
              </h2>
              <button
                onClick={() => setEditingRepository(null)}
                disabled={isSavingEdit}
                className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-200 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {/* Repository Name */}
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Display Name
                </label>
                <input
                  type="text"
                  value={editingRepository.name}
                  onChange={(e) => setEditingRepository({ ...editingRepository, name: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-200/50 dark:border-surface-600/50 rounded-xl bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent transition-all duration-200 ease-[var(--ease-tahoe)]"
                />
              </div>

              {/* Default Branch */}
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Default Branch
                </label>
                <input
                  type="text"
                  value={editingRepository.branch}
                  onChange={(e) => setEditingRepository({ ...editingRepository, branch: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-200/50 dark:border-surface-600/50 rounded-xl bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent transition-all duration-200 ease-[var(--ease-tahoe)]"
                />
              </div>

              {/* Scan Frequency */}
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Scan Frequency
                </label>
                <select
                  value={editingRepository.scanFrequency}
                  onChange={(e) => setEditingRepository({ ...editingRepository, scanFrequency: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-200/50 dark:border-surface-600/50 rounded-xl bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  <option value={ScanFrequency.ON_PUSH}>On Push</option>
                  <option value={ScanFrequency.DAILY}>Daily</option>
                  <option value={ScanFrequency.WEEKLY}>Weekly</option>
                  <option value={ScanFrequency.MANUAL}>Manual Only</option>
                </select>
              </div>

              {/* Clone URL (read-only) */}
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Clone URL
                </label>
                <input
                  type="text"
                  value={editingRepository.clone_url}
                  disabled
                  className="w-full px-3 py-2 border border-surface-200/50 dark:border-surface-700/30 rounded-xl bg-surface-100/50 dark:bg-surface-800/50 text-surface-500 dark:text-surface-400 cursor-not-allowed"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-surface-100/50 dark:border-surface-700/30">
              <button
                onClick={() => setEditingRepository(null)}
                disabled={isSavingEdit}
                className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                disabled={isSavingEdit}
                className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-xl hover:bg-aura-700 hover:-translate-y-px hover:shadow-md active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)] flex items-center gap-2"
              >
                {isSavingEdit ? (
                  <>
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save Changes'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default RepositoriesList;
