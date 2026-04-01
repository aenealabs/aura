/**
 * Project Aura - Connect Provider Step
 *
 * Step 1 of the Repository Onboarding Wizard.
 * Allows users to connect via OAuth (GitHub/GitLab) or manual URL+token.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

import { useState } from 'react';
import { useRepositories } from '../../../context/RepositoryContext';

const ConnectProviderStep = () => {
  const {
    provider,
    connection: _connection,
    connections,
    isWizardLoading,
    wizardError,
    selectProvider,
    initiateOAuth,
    setConnection,
    nextStep,
  } = useRepositories();

  const [manualUrl, setManualUrl] = useState('');
  const [manualToken, setManualToken] = useState('');
  const [manualError, setManualError] = useState(null);

  // Check for existing connections
  const githubConnections = connections.filter((c) => c.provider === 'github');
  const gitlabConnections = connections.filter((c) => c.provider === 'gitlab');

  const handleProviderSelect = (selectedProvider) => {
    selectProvider(selectedProvider);
    setManualError(null);
  };

  const handleOAuthConnect = async (providerType) => {
    await initiateOAuth(providerType);
  };

  const handleUseExistingConnection = (existingConnection) => {
    setConnection(existingConnection);
    nextStep();
  };

  const handleManualConnect = () => {
    // Validate URL
    if (!manualUrl.trim()) {
      setManualError('Repository URL is required');
      return;
    }

    // Basic URL validation
    const urlPattern = /^https?:\/\/.+\/.+/;
    if (!urlPattern.test(manualUrl)) {
      setManualError('Please enter a valid repository URL (e.g., https://github.com/org/repo)');
      return;
    }

    // Set manual connection
    setConnection({
      connection_id: 'manual',
      provider: 'manual',
      provider_username: 'manual',
      clone_url: manualUrl,
      token: manualToken,
      status: 'connected',
    });

    nextStep();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
          Connect Your Code Repository
        </h2>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
          Choose how you want to connect your repository for code analysis.
        </p>
      </div>

      {wizardError && (
        <div className="p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
          <p className="text-sm text-critical-700 dark:text-critical-400">{wizardError}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* GitHub Card */}
        <div
          className={`relative p-6 border-2 rounded-lg cursor-pointer transition-all ${
            provider === 'github'
              ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
              : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
          }`}
          onClick={() => handleProviderSelect('github')}
        >
          <div className="flex flex-col items-center space-y-3">
            <svg className="w-12 h-12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
            </svg>
            <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100">GitHub</h3>
            <p className="text-sm text-surface-500 dark:text-surface-400 text-center">
              Connect with your GitHub account
            </p>
            {githubConnections.length > 0 && (
              <span className="text-xs text-olive-600 dark:text-olive-400">
                {githubConnections.length} connection(s) available
              </span>
            )}
          </div>
          {provider === 'github' && (
            <div className="absolute top-2 right-2">
              <svg className="w-5 h-5 text-aura-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
          )}
        </div>

        {/* GitLab Card */}
        <div
          className={`relative p-6 border-2 rounded-lg cursor-pointer transition-all ${
            provider === 'gitlab'
              ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
              : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
          }`}
          onClick={() => handleProviderSelect('gitlab')}
        >
          <div className="flex flex-col items-center space-y-3">
            <svg className="w-12 h-12 text-warning-600" viewBox="0 0 24 24" fill="currentColor">
              <path d="m23.546 10.93-1.73-5.326-3.401-10.47a.483.483 0 0 0-.919 0l-3.402 10.47H9.908L6.506-5.134a.483.483 0 0 0-.919 0L2.185 5.604.455 10.93a.93.93 0 0 0 .338 1.04L12 19.87l11.207-7.9a.93.93 0 0 0 .339-1.04z" />
            </svg>
            <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100">GitLab</h3>
            <p className="text-sm text-surface-500 dark:text-surface-400 text-center">
              Connect with your GitLab account
            </p>
            {gitlabConnections.length > 0 && (
              <span className="text-xs text-olive-600 dark:text-olive-400">
                {gitlabConnections.length} connection(s) available
              </span>
            )}
          </div>
          {provider === 'gitlab' && (
            <div className="absolute top-2 right-2">
              <svg className="w-5 h-5 text-aura-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
          )}
        </div>

        {/* Manual URL Card */}
        <div
          className={`relative p-6 border-2 rounded-lg cursor-pointer transition-all ${
            provider === 'manual'
              ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
              : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
          }`}
          onClick={() => handleProviderSelect('manual')}
        >
          <div className="flex flex-col items-center space-y-3">
            <svg className="w-12 h-12 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100">Manual URL</h3>
            <p className="text-sm text-surface-500 dark:text-surface-400 text-center">
              Enter repository URL directly
            </p>
          </div>
          {provider === 'manual' && (
            <div className="absolute top-2 right-2">
              <svg className="w-5 h-5 text-aura-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
          )}
        </div>
      </div>

      {/* Provider-specific content */}
      {provider === 'github' && (
        <div className="mt-6 space-y-4">
          {githubConnections.length > 0 ? (
            <div className="space-y-3">
              <p className="text-sm font-medium text-surface-700 dark:text-surface-300">
                Use an existing connection:
              </p>
              {githubConnections.map((conn) => (
                <button
                  key={conn.connection_id}
                  onClick={() => handleUseExistingConnection(conn)}
                  className="w-full flex items-center justify-between p-3 border border-surface-200 dark:border-surface-700 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-800"
                >
                  <span className="text-sm text-surface-900 dark:text-surface-100">
                    @{conn.provider_username}
                  </span>
                  <span className="text-xs text-surface-500">Connected</span>
                </button>
              ))}
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-surface-300 dark:border-surface-600"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-white dark:bg-surface-900 text-surface-500">or</span>
                </div>
              </div>
            </div>
          ) : null}
          <button
            onClick={() => handleOAuthConnect('github')}
            disabled={isWizardLoading}
            className="w-full flex items-center justify-center px-4 py-3 border border-transparent rounded-lg shadow-sm text-white bg-surface-900 hover:bg-surface-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-surface-500 disabled:opacity-50"
          >
            {isWizardLoading ? (
              <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            ) : (
              <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
            )}
            Connect New GitHub Account
          </button>
        </div>
      )}

      {provider === 'gitlab' && (
        <div className="mt-6 space-y-4">
          {gitlabConnections.length > 0 ? (
            <div className="space-y-3">
              <p className="text-sm font-medium text-surface-700 dark:text-surface-300">
                Use an existing connection:
              </p>
              {gitlabConnections.map((conn) => (
                <button
                  key={conn.connection_id}
                  onClick={() => handleUseExistingConnection(conn)}
                  className="w-full flex items-center justify-between p-3 border border-surface-200 dark:border-surface-700 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-800"
                >
                  <span className="text-sm text-surface-900 dark:text-surface-100">
                    @{conn.provider_username}
                  </span>
                  <span className="text-xs text-surface-500">Connected</span>
                </button>
              ))}
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-surface-300 dark:border-surface-600"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-white dark:bg-surface-900 text-surface-500">or</span>
                </div>
              </div>
            </div>
          ) : null}
          <button
            onClick={() => handleOAuthConnect('gitlab')}
            disabled={isWizardLoading}
            className="w-full flex items-center justify-center px-4 py-3 border border-transparent rounded-lg shadow-sm text-white bg-warning-600 hover:bg-warning-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-warning-500 disabled:opacity-50"
          >
            {isWizardLoading ? (
              <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            ) : (
              <svg className="w-5 h-5 mr-2 text-warning-200" viewBox="0 0 24 24" fill="currentColor">
                <path d="m23.546 10.93-1.73-5.326-3.401-10.47a.483.483 0 0 0-.919 0l-3.402 10.47H9.908L6.506-5.134a.483.483 0 0 0-.919 0L2.185 5.604.455 10.93a.93.93 0 0 0 .338 1.04L12 19.87l11.207-7.9a.93.93 0 0 0 .339-1.04z" />
              </svg>
            )}
            Connect New GitLab Account
          </button>
        </div>
      )}

      {provider === 'manual' && (
        <div className="mt-6 space-y-4">
          {manualError && (
            <div className="p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
              <p className="text-sm text-critical-700 dark:text-critical-400">{manualError}</p>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Repository URL
            </label>
            <input
              type="url"
              value={manualUrl}
              onChange={(e) => {
                setManualUrl(e.target.value);
                setManualError(null);
              }}
              placeholder="https://github.com/organization/repository"
              className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg focus:ring-2 focus:ring-aura-500 focus:border-transparent dark:bg-surface-800 dark:text-surface-100"
            />
            <p className="mt-1 text-xs text-surface-500">
              Enter the full HTTPS URL of your repository
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Personal Access Token (Optional)
            </label>
            <input
              type="password"
              value={manualToken}
              onChange={(e) => setManualToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
              className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg focus:ring-2 focus:ring-aura-500 focus:border-transparent dark:bg-surface-800 dark:text-surface-100"
            />
            <p className="mt-1 text-xs text-surface-500">
              Required for private repositories. Token needs read access to repository contents.
            </p>
          </div>
          <button
            onClick={handleManualConnect}
            disabled={isWizardLoading}
            className="w-full flex items-center justify-center px-4 py-3 border border-transparent rounded-lg shadow-sm text-white bg-aura-600 hover:bg-aura-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-aura-500 disabled:opacity-50"
          >
            Continue with Manual URL
          </button>
        </div>
      )}
    </div>
  );
};

export default ConnectProviderStep;
