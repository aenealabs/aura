/**
 * Project Aura - DiagramGitDialog Component (ADR-060 Phase 4)
 *
 * Dialog for committing diagrams to GitHub/GitLab repositories.
 * Supports OAuth connections and pull request creation.
 *
 * Design System: Apple-inspired with clean typography, generous spacing,
 * and smooth transitions per design-principles.md
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useTheme } from '../../context/ThemeContext';
import {
  CodeBracketIcon,
  FolderIcon,
  DocumentTextIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  XMarkIcon,
  LinkIcon,
  CloudArrowUpIcon,
  DocumentPlusIcon,
} from '@heroicons/react/24/outline';

// ============================================================================
// Constants
// ============================================================================

const GIT_PROVIDERS = {
  github: {
    name: 'GitHub',
    icon: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
      </svg>
    ),
  },
  gitlab: {
    name: 'GitLab',
    icon: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="m23.546 10.93-1.533-4.716L20.48 1.496a.493.493 0 0 0-.945 0l-1.533 4.718H5.998L4.465 1.496a.493.493 0 0 0-.945 0L1.987 6.214.454 10.93a.949.949 0 0 0 .345 1.062l11.2 8.14 11.201-8.14a.949.949 0 0 0 .346-1.062z" />
      </svg>
    ),
  },
};

const COMMIT_STATUS = {
  idle: 'idle',
  committing: 'committing',
  success: 'success',
  error: 'error',
};

// ============================================================================
// RepositorySelector Component
// ============================================================================

function RepositorySelector({
  connections,
  selectedConnection,
  onSelectConnection,
  repositories,
  selectedRepository,
  onSelectRepository,
  isLoading,
  onRefresh,
}) {
  return (
    <div className="space-y-4">
      {/* Connection Selection */}
      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
          Git Connection
        </label>
        <div className="space-y-2">
          {connections.length === 0 ? (
            <p className="text-sm text-surface-500 italic">
              No Git connections configured.{' '}
              <a href="/settings/integrations" className="text-aura-500 hover:underline">
                Add a connection
              </a>
            </p>
          ) : (
            connections.map((conn) => (
              <button
                key={conn.connectionId}
                onClick={() => onSelectConnection(conn)}
                className={`
                  w-full flex items-center gap-3 p-3 rounded-lg border
                  transition-all duration-200
                  ${
                    selectedConnection?.connectionId === conn.connectionId
                      ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                      : 'border-surface-200 dark:border-surface-700 hover:border-aura-300'
                  }
                `}
              >
                <span className="text-surface-600 dark:text-surface-400">
                  {GIT_PROVIDERS[conn.provider]?.icon}
                </span>
                <div className="flex-1 text-left">
                  <div className="font-medium text-surface-900 dark:text-white">
                    {conn.providerUsername}
                  </div>
                  <div className="text-xs text-surface-500">
                    {GIT_PROVIDERS[conn.provider]?.name}
                  </div>
                </div>
                {selectedConnection?.connectionId === conn.connectionId && (
                  <CheckCircleIcon className="w-5 h-5 text-aura-500" />
                )}
              </button>
            ))
          )}
        </div>
      </div>

      {/* Repository Selection */}
      {selectedConnection && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
              Repository
            </label>
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="text-xs text-aura-500 hover:text-aura-600 flex items-center gap-1"
            >
              <ArrowPathIcon className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
          <select
            value={selectedRepository?.fullName || ''}
            onChange={(e) => {
              const repo = repositories.find((r) => r.fullName === e.target.value);
              onSelectRepository(repo);
            }}
            disabled={isLoading}
            className="
              w-full px-3 py-2 rounded-lg
              bg-white dark:bg-surface-800
              border border-surface-200 dark:border-surface-700
              text-surface-900 dark:text-white
              focus:outline-none focus:ring-2 focus:ring-aura-500
              disabled:opacity-50
            "
          >
            <option value="">Select a repository...</option>
            {repositories.map((repo) => (
              <option key={repo.fullName} value={repo.fullName}>
                {repo.fullName}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// CommitForm Component
// ============================================================================

function CommitForm({
  filePath,
  onFilePathChange,
  commitMessage,
  onCommitMessageChange,
  branch,
  onBranchChange,
  createPr,
  onCreatePrChange,
  prTitle,
  onPrTitleChange,
  prDescription,
  onPrDescriptionChange,
}) {
  return (
    <div className="space-y-4">
      {/* File Path */}
      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
          <FolderIcon className="w-4 h-4 inline-block mr-1" />
          File Path
        </label>
        <input
          type="text"
          value={filePath}
          onChange={(e) => onFilePathChange(e.target.value)}
          placeholder="docs/diagrams/architecture.svg"
          className="
            w-full px-3 py-2 rounded-lg
            bg-white dark:bg-surface-800
            border border-surface-200 dark:border-surface-700
            text-surface-900 dark:text-white
            placeholder:text-surface-400
            focus:outline-none focus:ring-2 focus:ring-aura-500
          "
        />
        <p className="mt-1 text-xs text-surface-500">
          Path where the diagram will be saved in the repository
        </p>
      </div>

      {/* Branch */}
      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
          <CodeBracketIcon className="w-4 h-4 inline-block mr-1" />
          Branch
        </label>
        <input
          type="text"
          value={branch}
          onChange={(e) => onBranchChange(e.target.value)}
          placeholder="main"
          className="
            w-full px-3 py-2 rounded-lg
            bg-white dark:bg-surface-800
            border border-surface-200 dark:border-surface-700
            text-surface-900 dark:text-white
            placeholder:text-surface-400
            focus:outline-none focus:ring-2 focus:ring-aura-500
          "
        />
      </div>

      {/* Commit Message */}
      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
          <DocumentTextIcon className="w-4 h-4 inline-block mr-1" />
          Commit Message
        </label>
        <textarea
          value={commitMessage}
          onChange={(e) => onCommitMessageChange(e.target.value)}
          placeholder="Add architecture diagram"
          rows={3}
          className="
            w-full px-3 py-2 rounded-lg
            bg-white dark:bg-surface-800
            border border-surface-200 dark:border-surface-700
            text-surface-900 dark:text-white
            placeholder:text-surface-400
            focus:outline-none focus:ring-2 focus:ring-aura-500
            resize-none
          "
        />
      </div>

      {/* Create PR Toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => onCreatePrChange(!createPr)}
          className={`
            relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full
            border-2 border-transparent transition-colors duration-200 ease-in-out
            focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
            ${createPr ? 'bg-aura-500' : 'bg-surface-200 dark:bg-surface-700'}
          `}
          role="switch"
          aria-checked={createPr}
        >
          <span
            className={`
              pointer-events-none inline-block h-5 w-5 transform rounded-full
              bg-white shadow ring-0 transition duration-200 ease-in-out
              ${createPr ? 'translate-x-5' : 'translate-x-0'}
            `}
          />
        </button>
        <span className="text-sm text-surface-700 dark:text-surface-300">
          Create Pull Request
        </span>
      </div>

      {/* PR Details (if creating PR) */}
      {createPr && (
        <div className="space-y-4 pl-4 border-l-2 border-aura-200 dark:border-aura-800">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              PR Title
            </label>
            <input
              type="text"
              value={prTitle}
              onChange={(e) => onPrTitleChange(e.target.value)}
              placeholder="Add architecture diagram"
              className="
                w-full px-3 py-2 rounded-lg
                bg-white dark:bg-surface-800
                border border-surface-200 dark:border-surface-700
                text-surface-900 dark:text-white
                placeholder:text-surface-400
                focus:outline-none focus:ring-2 focus:ring-aura-500
              "
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              PR Description
            </label>
            <textarea
              value={prDescription}
              onChange={(e) => onPrDescriptionChange(e.target.value)}
              placeholder="This PR adds the architecture diagram for..."
              rows={3}
              className="
                w-full px-3 py-2 rounded-lg
                bg-white dark:bg-surface-800
                border border-surface-200 dark:border-surface-700
                text-surface-900 dark:text-white
                placeholder:text-surface-400
                focus:outline-none focus:ring-2 focus:ring-aura-500
                resize-none
              "
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// CommitResult Component
// ============================================================================

function CommitResult({ result, onClose }) {
  if (!result) return null;

  const isSuccess = result.success;

  return (
    <div
      className={`
        p-4 rounded-lg
        ${isSuccess ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'}
      `}
    >
      <div className="flex items-start gap-3">
        {isSuccess ? (
          <CheckCircleIcon className="w-6 h-6 text-green-500 flex-shrink-0" />
        ) : (
          <ExclamationCircleIcon className="w-6 h-6 text-red-500 flex-shrink-0" />
        )}
        <div className="flex-1">
          <h4
            className={`
            font-medium
            ${isSuccess ? 'text-green-800 dark:text-green-200' : 'text-red-800 dark:text-red-200'}
          `}
          >
            {isSuccess ? 'Diagram committed successfully!' : 'Commit failed'}
          </h4>
          {isSuccess ? (
            <div className="mt-2 space-y-2 text-sm text-green-700 dark:text-green-300">
              {result.commitSha && (
                <p>
                  Commit:{' '}
                  <a
                    href={result.commitUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono underline hover:no-underline"
                  >
                    {result.commitSha.substring(0, 7)}
                  </a>
                </p>
              )}
              {result.fileUrl && (
                <p>
                  <a
                    href={result.fileUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-aura-500 hover:underline"
                  >
                    <LinkIcon className="w-4 h-4" />
                    View file
                  </a>
                </p>
              )}
              {result.prUrl && (
                <p>
                  <a
                    href={result.prUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-aura-500 hover:underline"
                  >
                    <DocumentPlusIcon className="w-4 h-4" />
                    View Pull Request #{result.prNumber}
                  </a>
                </p>
              )}
            </div>
          ) : (
            <p className="mt-1 text-sm text-red-700 dark:text-red-300">{result.error}</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// DiagramGitDialog Component
// ============================================================================

export default function DiagramGitDialog({
  isOpen,
  onClose,
  diagramContent,
  diagramName = 'architecture',
  contentType = 'svg',
}) {
  const { isDarkMode } = useTheme();

  // State
  const [connections, setConnections] = useState([]);
  const [selectedConnection, setSelectedConnection] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [selectedRepository, setSelectedRepository] = useState(null);
  const [isLoadingRepos, setIsLoadingRepos] = useState(false);

  // Form state
  const [filePath, setFilePath] = useState(`docs/diagrams/${diagramName}.${contentType}`);
  const [branch, setBranch] = useState('main');
  const [commitMessage, setCommitMessage] = useState(`Add ${diagramName} diagram`);
  const [createPr, setCreatePr] = useState(false);
  const [prTitle, setPrTitle] = useState(`Add ${diagramName} diagram`);
  const [prDescription, setPrDescription] = useState('');

  // Commit state
  const [commitStatus, setCommitStatus] = useState(COMMIT_STATUS.idle);
  const [commitResult, setCommitResult] = useState(null);

  // Load connections on mount
  useEffect(() => {
    async function loadConnections() {
      try {
        const response = await fetch('/api/v1/oauth/connections');
        if (response.ok) {
          const data = await response.json();
          setConnections(data.connections || []);
        }
      } catch (error) {
        console.error('Failed to load OAuth connections:', error);
      }
    }
    if (isOpen) {
      loadConnections();
    }
  }, [isOpen]);

  // Load repositories when connection changes
  useEffect(() => {
    async function loadRepositories() {
      if (!selectedConnection) {
        setRepositories([]);
        return;
      }

      setIsLoadingRepos(true);
      try {
        const response = await fetch(
          `/api/v1/oauth/${selectedConnection.connectionId}/repositories`
        );
        if (response.ok) {
          const data = await response.json();
          setRepositories(data.repositories || []);
        }
      } catch (error) {
        console.error('Failed to load repositories:', error);
      } finally {
        setIsLoadingRepos(false);
      }
    }
    loadRepositories();
  }, [selectedConnection]);

  // Handle commit
  const handleCommit = useCallback(async () => {
    if (!selectedConnection || !selectedRepository) return;

    setCommitStatus(COMMIT_STATUS.committing);
    setCommitResult(null);

    try {
      const [owner, name] = selectedRepository.fullName.split('/');

      const response = await fetch('/api/v1/diagrams/git/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connectionId: selectedConnection.connectionId,
          repoOwner: owner,
          repoName: name,
          filePath,
          diagramContent,
          contentType,
          commitMessage,
          branch,
          createPr,
          prTitle: createPr ? prTitle : undefined,
          prDescription: createPr ? prDescription : undefined,
        }),
      });

      const result = await response.json();

      if (response.ok && result.success) {
        setCommitStatus(COMMIT_STATUS.success);
        setCommitResult(result);
      } else {
        setCommitStatus(COMMIT_STATUS.error);
        setCommitResult({
          success: false,
          error: result.error || 'Failed to commit diagram',
        });
      }
    } catch (error) {
      setCommitStatus(COMMIT_STATUS.error);
      setCommitResult({
        success: false,
        error: error.message || 'Network error',
      });
    }
  }, [
    selectedConnection,
    selectedRepository,
    filePath,
    diagramContent,
    contentType,
    commitMessage,
    branch,
    createPr,
    prTitle,
    prDescription,
  ]);

  // Reset state on close
  const handleClose = useCallback(() => {
    setCommitStatus(COMMIT_STATUS.idle);
    setCommitResult(null);
    onClose();
  }, [onClose]);

  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        handleClose();
      }
    }
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleClose]);

  if (!isOpen) return null;

  const canCommit =
    selectedConnection &&
    selectedRepository &&
    filePath &&
    commitMessage &&
    commitStatus !== COMMIT_STATUS.committing;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="git-dialog-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Dialog */}
      <div
        className="
          relative w-full max-w-lg max-h-[90vh] overflow-hidden
          bg-white dark:bg-surface-800
          rounded-2xl shadow-2xl
          flex flex-col
        "
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
          <h2
            id="git-dialog-title"
            className="text-lg font-semibold text-surface-900 dark:text-white flex items-center gap-2"
          >
            <CloudArrowUpIcon className="w-5 h-5 text-aura-500" />
            Commit to Repository
          </h2>
          <button
            onClick={handleClose}
            className="p-1 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            aria-label="Close dialog"
          >
            <XMarkIcon className="w-5 h-5 text-surface-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          {/* Result Banner */}
          {commitResult && <CommitResult result={commitResult} onClose={() => setCommitResult(null)} />}

          {/* Repository Selection */}
          {!commitResult?.success && (
            <>
              <RepositorySelector
                connections={connections}
                selectedConnection={selectedConnection}
                onSelectConnection={setSelectedConnection}
                repositories={repositories}
                selectedRepository={selectedRepository}
                onSelectRepository={setSelectedRepository}
                isLoading={isLoadingRepos}
                onRefresh={() => {
                  setSelectedConnection((c) => ({ ...c }));
                }}
              />

              {/* Commit Form */}
              {selectedRepository && (
                <CommitForm
                  filePath={filePath}
                  onFilePathChange={setFilePath}
                  commitMessage={commitMessage}
                  onCommitMessageChange={setCommitMessage}
                  branch={branch}
                  onBranchChange={setBranch}
                  createPr={createPr}
                  onCreatePrChange={setCreatePr}
                  prTitle={prTitle}
                  onPrTitleChange={setPrTitle}
                  prDescription={prDescription}
                  onPrDescriptionChange={setPrDescription}
                />
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-surface-200 dark:border-surface-700">
          {commitResult?.success ? (
            <button
              onClick={handleClose}
              className="
                px-4 py-2 rounded-lg
                bg-aura-500 text-white
                hover:bg-aura-600
                transition-colors duration-200
              "
            >
              Done
            </button>
          ) : (
            <>
              <button
                onClick={handleClose}
                className="
                  px-4 py-2 rounded-lg
                  text-surface-600 dark:text-surface-400
                  hover:bg-surface-100 dark:hover:bg-surface-700
                  transition-colors duration-200
                "
              >
                Cancel
              </button>
              <button
                onClick={handleCommit}
                disabled={!canCommit}
                className="
                  px-4 py-2 rounded-lg
                  bg-aura-500 text-white
                  hover:bg-aura-600
                  disabled:opacity-50 disabled:cursor-not-allowed
                  transition-colors duration-200
                  flex items-center gap-2
                "
              >
                {commitStatus === COMMIT_STATUS.committing ? (
                  <>
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                    Committing...
                  </>
                ) : (
                  <>
                    <CloudArrowUpIcon className="w-4 h-4" />
                    Commit
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Exports
// ============================================================================

export { RepositorySelector, CommitForm, CommitResult };
