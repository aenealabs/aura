/**
 * Project Aura - Select Repositories Step
 *
 * Step 2 of the Repository Onboarding Wizard.
 * Lists repositories from the OAuth provider for selection.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

import { useState, useEffect, useMemo } from 'react';
import { useRepositories } from '../../../context/RepositoryContext';
import { LanguageInfo } from '../../../services/repositoryApi';

const SelectRepositoriesStep = () => {
  const {
    connection,
    availableRepos,
    selectedRepos,
    isWizardLoading,
    wizardError,
    loadAvailableRepos,
    toggleRepoSelection,
    selectAllRepos,
    clearSelection,
    nextStep,
    prevStep,
  } = useRepositories();

  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('name'); // name, updated, language
  const [filterPrivate, setFilterPrivate] = useState('all'); // all, public, private

  // Load repositories when connection changes
  useEffect(() => {
    if (connection?.connection_id && connection.connection_id !== 'manual') {
      loadAvailableRepos(connection.connection_id);
    }
  }, [connection, loadAvailableRepos]);

  // Filter and sort repositories
  const filteredRepos = useMemo(() => {
    let repos = [...availableRepos];

    // Search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      repos = repos.filter(
        (repo) =>
          repo.name.toLowerCase().includes(term) ||
          repo.full_name.toLowerCase().includes(term) ||
          repo.description?.toLowerCase().includes(term)
      );
    }

    // Privacy filter
    if (filterPrivate === 'public') {
      repos = repos.filter((repo) => !repo.private);
    } else if (filterPrivate === 'private') {
      repos = repos.filter((repo) => repo.private);
    }

    // Sort
    repos.sort((a, b) => {
      switch (sortBy) {
        case 'updated':
          return new Date(b.last_pushed_at || 0) - new Date(a.last_pushed_at || 0);
        case 'language':
          return (a.language || 'zzz').localeCompare(b.language || 'zzz');
        case 'name':
        default:
          return a.name.localeCompare(b.name);
      }
    });

    return repos;
  }, [availableRepos, searchTerm, sortBy, filterPrivate]);

  const formatSize = (kb) => {
    if (kb < 1024) return `${kb} KB`;
    return `${(kb / 1024).toFixed(1)} MB`;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  };

  const canProceed = selectedRepos.length > 0;

  // Handle manual connection (single repo)
  if (connection?.connection_id === 'manual') {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
            Manual Repository Configuration
          </h2>
          <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
            Configure your manually entered repository.
          </p>
        </div>

        <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-lg">
          <p className="text-sm text-surface-700 dark:text-surface-300">
            <span className="font-medium">Repository URL:</span> {connection.clone_url}
          </p>
        </div>

        <div className="flex justify-between">
          <button
            onClick={prevStep}
            className="px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-800"
          >
            Back
          </button>
          <button
            onClick={nextStep}
            className="px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700"
          >
            Continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
          Select Repositories
        </h2>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
          Choose which repositories to analyze with Project Aura.
        </p>
      </div>

      {wizardError && (
        <div className="p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
          <p className="text-sm text-critical-700 dark:text-critical-400">{wizardError}</p>
        </div>
      )}

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search repositories..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg focus:ring-2 focus:ring-aura-500 focus:border-transparent dark:bg-surface-800 dark:text-surface-100"
          />
        </div>
        <div className="flex gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
          >
            <option value="name">Sort by Name</option>
            <option value="updated">Last Updated</option>
            <option value="language">Language</option>
          </select>
          <select
            value={filterPrivate}
            onChange={(e) => setFilterPrivate(e.target.value)}
            className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
          >
            <option value="all">All Repos</option>
            <option value="public">Public</option>
            <option value="private">Private</option>
          </select>
        </div>
      </div>

      {/* Selection Actions */}
      <div className="flex items-center justify-between py-2 border-b border-surface-200 dark:border-surface-700">
        <div className="text-sm text-surface-600 dark:text-surface-400">
          {selectedRepos.length} of {filteredRepos.filter((r) => !r.already_connected).length} selected
        </div>
        <div className="flex gap-2">
          <button
            onClick={selectAllRepos}
            className="text-sm text-aura-600 hover:text-aura-700 dark:text-aura-400"
          >
            Select All
          </button>
          <button
            onClick={clearSelection}
            className="text-sm text-surface-600 hover:text-surface-700 dark:text-surface-400"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Repository List */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {isWizardLoading ? (
          <div className="flex items-center justify-center py-8">
            <svg className="animate-spin h-8 w-8 text-aura-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          </div>
        ) : filteredRepos.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-surface-500 dark:text-surface-400">
              {searchTerm ? 'No repositories match your search.' : 'No repositories found.'}
            </p>
          </div>
        ) : (
          filteredRepos.map((repo) => {
            const isSelected = selectedRepos.includes(repo.id);
            const isDisabled = repo.already_connected;
            const langInfo = LanguageInfo[repo.language?.toLowerCase()] || null;

            return (
              <div
                key={repo.id}
                onClick={() => !isDisabled && toggleRepoSelection(repo.id)}
                className={`flex items-start p-4 border rounded-lg cursor-pointer transition-all ${
                  isDisabled
                    ? 'border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50 opacity-60 cursor-not-allowed'
                    : isSelected
                    ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                    : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
                }`}
              >
                <div className="flex-shrink-0 mt-1">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    disabled={isDisabled}
                    onChange={() => {}}
                    className="h-4 w-4 text-aura-600 rounded border-surface-300 focus:ring-aura-500"
                  />
                </div>
                <div className="ml-3 flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                      {repo.name}
                    </p>
                    {repo.private && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400">
                        Private
                      </span>
                    )}
                    {isDisabled && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-olive-100 dark:bg-olive-900/30 text-olive-600 dark:text-olive-400">
                        Already Connected
                      </span>
                    )}
                  </div>
                  {repo.description && (
                    <p className="mt-1 text-sm text-surface-500 dark:text-surface-400 truncate">
                      {repo.description}
                    </p>
                  )}
                  <div className="mt-2 flex items-center gap-4 text-xs text-surface-500 dark:text-surface-400">
                    {langInfo && (
                      <span className="flex items-center gap-1">
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: langInfo.color }}
                        />
                        {langInfo.name}
                      </span>
                    )}
                    <span>{formatSize(repo.size_kb)}</span>
                    <span>Updated {formatDate(repo.last_pushed_at)}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Navigation */}
      <div className="flex justify-between pt-4 border-t border-surface-200 dark:border-surface-700">
        <button
          onClick={prevStep}
          className="px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-800"
        >
          Back
        </button>
        <button
          onClick={nextStep}
          disabled={!canProceed}
          className="px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Continue ({selectedRepos.length} selected)
        </button>
      </div>
    </div>
  );
};

export default SelectRepositoriesStep;
