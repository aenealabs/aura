/**
 * Project Aura - Repository Card Component
 *
 * Displays a single repository in either grid or list view.
 * Shows status, language breakdown, and quick actions.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

import { useState } from 'react';
import { LanguageInfo, RepositoryStatus } from '../../services/repositoryApi';

const statusConfig = {
  [RepositoryStatus.ACTIVE]: {
    label: 'Active',
    color: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    icon: (
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
  [RepositoryStatus.SYNCING]: {
    label: 'Syncing',
    color: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    icon: (
      <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    ),
  },
  [RepositoryStatus.ERROR]: {
    label: 'Error',
    color: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    icon: (
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
  [RepositoryStatus.PENDING]: {
    label: 'Pending',
    color: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    icon: (
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
  [RepositoryStatus.ARCHIVED]: {
    label: 'Archived',
    color: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
    icon: (
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path d="M4 3a2 2 0 100 4h12a2 2 0 100-4H4z" />
        <path
          fillRule="evenodd"
          d="M3 8h14v7a2 2 0 01-2 2H5a2 2 0 01-2-2V8zm5 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
};

const providerIcons = {
  github: (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
    </svg>
  ),
  gitlab: (
    <svg className="w-5 h-5 text-warning-600" viewBox="0 0 24 24" fill="currentColor">
      <path d="m23.546 10.93-1.73-5.326-3.401-10.47a.483.483 0 0 0-.919 0l-3.402 10.47H9.908L6.506-5.134a.483.483 0 0 0-.919 0L2.185 5.604.455 10.93a.93.93 0 0 0 .338 1.04L12 19.87l11.207-7.9a.93.93 0 0 0 .339-1.04z" />
    </svg>
  ),
  manual: (
    <svg className="w-5 h-5 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
      />
    </svg>
  ),
};

const RepositoryCard = ({ repository, viewMode, onEdit, onDelete, onSync }) => {
  const [showActions, setShowActions] = useState(false);

  const status = statusConfig[repository.status] || statusConfig[RepositoryStatus.PENDING];

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatSize = (kb) => {
    if (!kb) return 'Unknown';
    if (kb < 1024) return `${kb} KB`;
    if (kb < 1024 * 1024) return `${(kb / 1024).toFixed(1)} MB`;
    return `${(kb / 1024 / 1024).toFixed(1)} GB`;
  };

  // Grid view card
  if (viewMode === 'grid') {
    return (
      <div
        className="relative p-4 bg-white dark:bg-surface-800 backdrop-blur-xl border border-surface-200/50 dark:border-surface-700/30 rounded-xl shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] hover:-translate-y-px transition-all duration-200 ease-[var(--ease-tahoe)]"
        onMouseEnter={() => setShowActions(true)}
        onMouseLeave={() => setShowActions(false)}
      >
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <span className="flex-shrink-0 text-surface-600 dark:text-surface-400">
              {providerIcons[repository.provider] || providerIcons.manual}
            </span>
            <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
              {repository.name}
            </h3>
          </div>
          <span
            className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${status.color}`}
          >
            {status.icon}
            {status.label}
          </span>
        </div>

        {/* Clone URL */}
        <p className="mt-2 text-xs text-surface-500 dark:text-surface-400 truncate">
          {repository.clone_url}
        </p>

        {/* Languages */}
        {repository.languages && repository.languages.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {repository.languages.slice(0, 4).map((lang) => {
              const info = LanguageInfo[lang];
              return (
                <span
                  key={lang}
                  className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400"
                >
                  {info?.name || lang}
                </span>
              );
            })}
            {repository.languages.length > 4 && (
              <span className="text-xs text-surface-500">+{repository.languages.length - 4}</span>
            )}
          </div>
        )}

        {/* Stats */}
        <div className="mt-3 flex items-center gap-4 text-xs text-surface-500 dark:text-surface-400">
          {repository.files_count && (
            <span>{repository.files_count.toLocaleString()} files</span>
          )}
          {repository.size_kb && <span>{formatSize(repository.size_kb)}</span>}
        </div>

        {/* Last Sync */}
        <div className="mt-2 text-xs text-surface-400 dark:text-surface-500">
          Last sync: {formatDate(repository.last_sync)}
        </div>

        {/* Hover Actions */}
        {showActions && (
          <div className="absolute top-2 right-2 flex items-center gap-1 bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl rounded-xl shadow-[var(--shadow-glass-hover)] p-1 border border-white/50 dark:border-surface-700/50">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onSync();
              }}
              className="p-1.5 text-surface-500 hover:text-aura-600 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
              title="Sync Now"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onEdit();
              }}
              className="p-1.5 text-surface-500 hover:text-surface-700 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
              title="Edit"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="p-1.5 text-surface-500 hover:text-critical-600 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
              title="Delete"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
          </div>
        )}
      </div>
    );
  }

  // List view row
  return (
    <div className="flex items-center justify-between p-3 bg-white dark:bg-surface-800 backdrop-blur-xl border border-surface-200/50 dark:border-surface-700/30 rounded-xl shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] hover:-translate-y-px transition-all duration-200 ease-[var(--ease-tahoe)]">
      {/* Left section */}
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <span className="flex-shrink-0 text-surface-600 dark:text-surface-400">
          {providerIcons[repository.provider] || providerIcons.manual}
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
              {repository.name}
            </h3>
            <span
              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${status.color}`}
            >
              {status.icon}
              {status.label}
            </span>
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400 truncate">
            {repository.clone_url}
          </p>
        </div>
      </div>

      {/* Middle section - stats */}
      <div className="hidden md:flex items-center gap-6 mx-4 text-xs text-surface-500 dark:text-surface-400">
        {repository.languages && repository.languages.length > 0 && (
          <div className="flex items-center gap-1">
            {repository.languages.slice(0, 3).map((lang) => {
              const info = LanguageInfo[lang];
              return (
                <span
                  key={lang}
                  className="px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-700"
                >
                  {info?.name || lang}
                </span>
              );
            })}
            {repository.languages.length > 3 && (
              <span>+{repository.languages.length - 3}</span>
            )}
          </div>
        )}
        <span>{repository.files_count?.toLocaleString() || '-'} files</span>
        <span>{formatSize(repository.size_kb)}</span>
        <span>Synced: {formatDate(repository.last_sync)}</span>
      </div>

      {/* Right section - actions */}
      <div className="flex items-center gap-1">
        <button
          onClick={onSync}
          className="p-2 text-surface-500 hover:text-aura-600 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
          title="Sync Now"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
        <button
          onClick={onEdit}
          className="p-2 text-surface-500 hover:text-surface-700 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
          title="Edit"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            />
          </svg>
        </button>
        <button
          onClick={onDelete}
          className="p-2 text-surface-500 hover:text-critical-600 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
          title="Delete"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default RepositoryCard;
