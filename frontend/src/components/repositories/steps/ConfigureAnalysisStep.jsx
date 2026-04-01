/**
 * Project Aura - Configure Analysis Step
 *
 * Step 3 of the Repository Onboarding Wizard.
 * Configure analysis settings for selected repositories.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

import { useState } from 'react';
import { useRepositories } from '../../../context/RepositoryContext';
import { DEFAULT_REPOSITORY_CONFIG, ScanFrequency, LanguageInfo } from '../../../services/repositoryApi';

const ConfigureAnalysisStep = () => {
  const {
    connection,
    availableRepos,
    selectedRepos,
    repoConfigs,
    updateRepoConfig,
    applyConfigToAll,
    nextStep,
    prevStep,
  } = useRepositories();

  const [activeRepoId, setActiveRepoId] = useState(selectedRepos[0] || null);
  const [applyToAll, setApplyToAll] = useState(false);

  // Get selected repository objects
  const selectedRepoObjects = availableRepos.filter((r) => selectedRepos.includes(r.id));

  // Get current config for active repo
  const activeConfig = activeRepoId ? repoConfigs[activeRepoId] || DEFAULT_REPOSITORY_CONFIG : DEFAULT_REPOSITORY_CONFIG;

  const handleConfigChange = (field, value) => {
    if (applyToAll) {
      applyConfigToAll({ [field]: value });
    } else if (activeRepoId) {
      updateRepoConfig(activeRepoId, { [field]: value });
    }
  };

  const handleLanguageToggle = (language) => {
    const currentLanguages = activeConfig.languages || [];
    const newLanguages = currentLanguages.includes(language)
      ? currentLanguages.filter((l) => l !== language)
      : [...currentLanguages, language];

    handleConfigChange('languages', newLanguages);
  };

  const handleExcludePatternsChange = (value) => {
    const patterns = value.split('\n').filter((p) => p.trim());
    handleConfigChange('excludePatterns', patterns);
  };

  // For manual connection, show simplified config
  if (connection?.connection_id === 'manual') {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
            Configure Analysis
          </h2>
          <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
            Set up how Project Aura should analyze your repository.
          </p>
        </div>

        <div className="space-y-4">
          {/* Branch */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Default Branch
            </label>
            <input
              type="text"
              value={activeConfig.branch}
              onChange={(e) => handleConfigChange('branch', e.target.value)}
              className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg focus:ring-2 focus:ring-aura-500 focus:border-transparent dark:bg-surface-800 dark:text-surface-100"
            />
          </div>

          {/* Languages */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Languages to Analyze
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(LanguageInfo).map(([key, info]) => (
                <label
                  key={key}
                  className={`flex items-center gap-2 p-2 border rounded-lg cursor-pointer ${
                    activeConfig.languages?.includes(key)
                      ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                      : 'border-surface-200 dark:border-surface-700'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={activeConfig.languages?.includes(key)}
                    onChange={() => handleLanguageToggle(key)}
                    className="h-4 w-4 text-aura-600 rounded border-surface-300"
                  />
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: info.color }}
                  />
                  <span className="text-sm text-surface-700 dark:text-surface-300">
                    {info.name}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Scan Frequency */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Scan Frequency
            </label>
            <select
              value={activeConfig.scanFrequency}
              onChange={(e) => handleConfigChange('scanFrequency', e.target.value)}
              className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
            >
              <option value={ScanFrequency.ON_PUSH}>On Push (Recommended)</option>
              <option value={ScanFrequency.DAILY}>Daily</option>
              <option value={ScanFrequency.WEEKLY}>Weekly</option>
              <option value={ScanFrequency.MANUAL}>Manual Only</option>
            </select>
          </div>
        </div>

        <div className="flex justify-between pt-4 border-t border-surface-200 dark:border-surface-700">
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
          Configure Analysis
        </h2>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
          Customize analysis settings for each repository.
        </p>
      </div>

      {/* Apply to All Toggle */}
      <div className="flex items-center gap-2 p-3 bg-surface-50 dark:bg-surface-800 rounded-lg">
        <input
          type="checkbox"
          id="applyToAll"
          checked={applyToAll}
          onChange={(e) => setApplyToAll(e.target.checked)}
          className="h-4 w-4 text-aura-600 rounded border-surface-300"
        />
        <label htmlFor="applyToAll" className="text-sm text-surface-700 dark:text-surface-300">
          Apply changes to all selected repositories
        </label>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Repository Tabs */}
        <div className="lg:col-span-1 space-y-2 max-h-96 overflow-y-auto">
          {selectedRepoObjects.map((repo) => (
            <button
              key={repo.id}
              onClick={() => setActiveRepoId(repo.id)}
              className={`w-full text-left p-3 rounded-lg transition-all ${
                activeRepoId === repo.id
                  ? 'bg-aura-50 dark:bg-aura-900/20 border-2 border-aura-500'
                  : 'bg-surface-50 dark:bg-surface-800 border-2 border-transparent hover:border-surface-300 dark:hover:border-surface-600'
              }`}
            >
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                {repo.name}
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                {repoConfigs[repo.id]?.branch || repo.default_branch || 'main'}
              </p>
            </button>
          ))}
        </div>

        {/* Configuration Panel */}
        <div className="lg:col-span-2 space-y-4">
          {activeRepoId ? (
            <>
              {/* Branch */}
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Branch
                </label>
                <input
                  type="text"
                  value={activeConfig.branch}
                  onChange={(e) => handleConfigChange('branch', e.target.value)}
                  className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg focus:ring-2 focus:ring-aura-500 focus:border-transparent dark:bg-surface-800 dark:text-surface-100"
                />
              </div>

              {/* Languages */}
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  Languages to Analyze
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {Object.entries(LanguageInfo).map(([key, info]) => (
                    <label
                      key={key}
                      className={`flex items-center gap-2 p-2 border rounded-lg cursor-pointer ${
                        activeConfig.languages?.includes(key)
                          ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                          : 'border-surface-200 dark:border-surface-700'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={activeConfig.languages?.includes(key)}
                        onChange={() => handleLanguageToggle(key)}
                        className="h-4 w-4 text-aura-600 rounded border-surface-300"
                      />
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: info.color }}
                      />
                      <span className="text-sm text-surface-700 dark:text-surface-300">
                        {info.name}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Scan Frequency */}
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Scan Frequency
                </label>
                <select
                  value={activeConfig.scanFrequency}
                  onChange={(e) => handleConfigChange('scanFrequency', e.target.value)}
                  className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
                >
                  <option value={ScanFrequency.ON_PUSH}>On Push (Recommended)</option>
                  <option value={ScanFrequency.DAILY}>Daily</option>
                  <option value={ScanFrequency.WEEKLY}>Weekly</option>
                  <option value={ScanFrequency.MANUAL}>Manual Only</option>
                </select>
              </div>

              {/* Exclude Patterns */}
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Exclude Patterns (one per line)
                </label>
                <textarea
                  value={(activeConfig.excludePatterns || []).join('\n')}
                  onChange={(e) => handleExcludePatternsChange(e.target.value)}
                  rows={4}
                  placeholder="node_modules/
dist/
*.min.js"
                  className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg focus:ring-2 focus:ring-aura-500 focus:border-transparent dark:bg-surface-800 dark:text-surface-100 font-mono text-sm"
                />
              </div>

              {/* Enable Webhook */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="enableWebhook"
                  checked={activeConfig.enableWebhook}
                  onChange={(e) => handleConfigChange('enableWebhook', e.target.checked)}
                  className="h-4 w-4 text-aura-600 rounded border-surface-300"
                />
                <label htmlFor="enableWebhook" className="text-sm text-surface-700 dark:text-surface-300">
                  Enable webhook for automatic updates on push
                </label>
              </div>
            </>
          ) : (
            <div className="text-center py-8 text-surface-500 dark:text-surface-400">
              Select a repository to configure
            </div>
          )}
        </div>
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
          className="px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700"
        >
          Review & Start Ingestion
        </button>
      </div>
    </div>
  );
};

export default ConfigureAnalysisStep;
