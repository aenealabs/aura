/**
 * Project Aura - Review Step
 *
 * Step 4 of the Repository Onboarding Wizard.
 * Review configuration before starting ingestion.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

import { useState } from 'react';
import { useRepositories } from '../../../context/RepositoryContext';
import { LanguageInfo, ScanFrequency } from '../../../services/repositoryApi';

const ReviewStep = () => {
  const {
    connection,
    availableRepos,
    selectedRepos,
    repoConfigs,
    isWizardLoading,
    wizardError,
    startIngestion,
    prevStep,
  } = useRepositories();

  const [confirmed, setConfirmed] = useState(false);

  // Get selected repository objects
  const selectedRepoObjects = availableRepos.filter((r) => selectedRepos.includes(r.id));

  // Calculate estimates
  const totalSizeKb = selectedRepoObjects.reduce((sum, r) => sum + (r.size_kb || 0), 0);
  const estimatedTimeMinutes = Math.max(1, Math.ceil(totalSizeKb / 1024 / 5)); // ~5MB per minute estimate

  const scanFrequencyLabels = {
    [ScanFrequency.ON_PUSH]: 'On Push',
    [ScanFrequency.DAILY]: 'Daily',
    [ScanFrequency.WEEKLY]: 'Weekly',
    [ScanFrequency.MANUAL]: 'Manual',
  };

  const formatSize = (kb) => {
    if (kb < 1024) return `${kb} KB`;
    if (kb < 1024 * 1024) return `${(kb / 1024).toFixed(1)} MB`;
    return `${(kb / 1024 / 1024).toFixed(1)} GB`;
  };

  const handleStartIngestion = async () => {
    if (!confirmed) return;
    await startIngestion();
  };

  // For manual connection
  if (connection?.connection_id === 'manual') {
    const manualConfig = repoConfigs['manual'] || {};

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
            Review Configuration
          </h2>
          <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
            Confirm your settings before starting ingestion.
          </p>
        </div>

        {wizardError && (
          <div className="p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
            <p className="text-sm text-critical-700 dark:text-critical-400">{wizardError}</p>
          </div>
        )}

        <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-lg space-y-3">
          <div>
            <p className="text-xs text-surface-500 uppercase">Repository URL</p>
            <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
              {connection.clone_url}
            </p>
          </div>
          <div>
            <p className="text-xs text-surface-500 uppercase">Branch</p>
            <p className="text-sm text-surface-900 dark:text-surface-100">
              {manualConfig.branch || 'main'}
            </p>
          </div>
          <div>
            <p className="text-xs text-surface-500 uppercase">Languages</p>
            <p className="text-sm text-surface-900 dark:text-surface-100">
              {(manualConfig.languages || []).join(', ') || 'All'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 p-4 bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800 rounded-lg">
          <input
            type="checkbox"
            id="confirm"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            className="h-4 w-4 text-aura-600 rounded border-surface-300"
          />
          <label htmlFor="confirm" className="text-sm text-warning-800 dark:text-warning-200">
            I confirm that I have authorization to analyze this repository.
          </label>
        </div>

        <div className="flex justify-between pt-4 border-t border-surface-200 dark:border-surface-700">
          <button
            onClick={prevStep}
            className="px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-800"
          >
            Back
          </button>
          <button
            onClick={handleStartIngestion}
            disabled={!confirmed || isWizardLoading}
            className="px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isWizardLoading && (
              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            )}
            Start Ingestion
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
          Review Configuration
        </h2>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
          Review your selections before starting ingestion.
        </p>
      </div>

      {wizardError && (
        <div className="p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
          <p className="text-sm text-critical-700 dark:text-critical-400">{wizardError}</p>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-lg text-center">
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            {selectedRepos.length}
          </p>
          <p className="text-sm text-surface-500">Repositories</p>
        </div>
        <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-lg text-center">
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            {formatSize(totalSizeKb)}
          </p>
          <p className="text-sm text-surface-500">Total Size</p>
        </div>
        <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-lg text-center">
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            ~{estimatedTimeMinutes} min
          </p>
          <p className="text-sm text-surface-500">Est. Time</p>
        </div>
      </div>

      {/* Connection Info */}
      <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-lg">
        <p className="text-xs text-surface-500 uppercase mb-1">Connected Account</p>
        <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
          @{connection?.provider_username} ({connection?.provider})
        </p>
      </div>

      {/* Repository List */}
      <div className="space-y-3 max-h-64 overflow-y-auto">
        {selectedRepoObjects.map((repo) => {
          const config = repoConfigs[repo.id] || {};
          return (
            <div
              key={repo.id}
              className="p-4 border border-surface-200 dark:border-surface-700 rounded-lg"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                    {repo.name}
                  </p>
                  <p className="text-xs text-surface-500 mt-1">
                    Branch: {config.branch || repo.default_branch || 'main'}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-surface-500">
                    {scanFrequencyLabels[config.scanFrequency] || 'On Push'}
                  </p>
                  {config.enableWebhook && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-olive-100 dark:bg-olive-900/30 text-olive-600 dark:text-olive-400 mt-1">
                      Webhook
                    </span>
                  )}
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {(config.languages || []).slice(0, 5).map((lang) => {
                  const info = LanguageInfo[lang];
                  return (
                    <span
                      key={lang}
                      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400"
                    >
                      {info?.name || lang}
                    </span>
                  );
                })}
                {(config.languages || []).length > 5 && (
                  <span className="text-xs text-surface-500">
                    +{config.languages.length - 5} more
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Webhook Warning */}
      {selectedRepoObjects.some((r) => repoConfigs[r.id]?.enableWebhook) && (
        <div className="p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
          <p className="text-sm text-aura-800 dark:text-aura-200">
            <strong>Note:</strong> Webhooks will be registered on repositories to enable automatic
            updates on push. This requires admin access to the repository.
          </p>
        </div>
      )}

      {/* Confirmation */}
      <div className="flex items-center gap-2 p-4 bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800 rounded-lg">
        <input
          type="checkbox"
          id="confirm"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
          className="h-4 w-4 text-aura-600 rounded border-surface-300"
        />
        <label htmlFor="confirm" className="text-sm text-warning-800 dark:text-warning-200">
          I confirm that I want to start ingestion for {selectedRepos.length} repository/repositories.
        </label>
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
          onClick={handleStartIngestion}
          disabled={!confirmed || isWizardLoading}
          className="px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {isWizardLoading && (
            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          )}
          Start Ingestion
        </button>
      </div>
    </div>
  );
};

export default ReviewStep;
