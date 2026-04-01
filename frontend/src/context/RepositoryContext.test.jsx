import { useEffect } from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { RepositoryProvider, useRepositories, WizardSteps } from './RepositoryContext';

// Mock the repositoryApi module
vi.mock('../services/repositoryApi', () => ({
  listRepositories: vi.fn(),
  listOAuthConnections: vi.fn(),
  initiateOAuth: vi.fn(),
  completeOAuth: vi.fn(),
  listAvailableRepositories: vi.fn(),
  startIngestion: vi.fn(),
  getIngestionStatus: vi.fn(),
  cancelIngestion: vi.fn(),
  deleteRepository: vi.fn(),
  triggerSync: vi.fn(),
  revokeOAuthConnection: vi.fn(),
  DEFAULT_REPOSITORY_CONFIG: {
    branch: 'main',
    languages: [],
    scanFrequency: 'daily',
    excludePatterns: [],
    enableWebhook: true,
  },
}));

import * as repositoryApi from '../services/repositoryApi';

// Test consumer component
function TestConsumer({ onMount }) {
  const context = useRepositories();

  useEffect(() => {
    if (onMount) onMount(context);
  }, [onMount, context]);

  return (
    <div>
      <span data-testid="is-wizard-open">{context.isWizardOpen ? 'true' : 'false'}</span>
      <span data-testid="current-step">{context.currentStep}</span>
      <span data-testid="provider">{context.provider || 'none'}</span>
      <span data-testid="repositories-count">{context.repositories.length}</span>
      <span data-testid="selected-repos-count">{context.selectedRepos.length}</span>
      <span data-testid="is-loading">{context.isLoadingRepositories ? 'true' : 'false'}</span>
      <span data-testid="error">{context.error || 'none'}</span>
      <button data-testid="open-wizard" onClick={() => context.openWizard()}>Open Wizard</button>
      <button data-testid="close-wizard" onClick={() => context.closeWizard()}>Close Wizard</button>
      <button data-testid="next-step" onClick={() => context.nextStep()}>Next Step</button>
      <button data-testid="prev-step" onClick={() => context.prevStep()}>Prev Step</button>
      <button data-testid="select-github" onClick={() => context.selectProvider('github')}>Select GitHub</button>
      <button data-testid="reset-wizard" onClick={() => context.resetWizard()}>Reset Wizard</button>
    </div>
  );
}

describe('RepositoryContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();

    // Default mock implementations
    repositoryApi.listRepositories.mockResolvedValue([]);
    repositoryApi.listOAuthConnections.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllTimers();
    localStorage.clear();
    sessionStorage.clear();
  });

  describe('RepositoryProvider', () => {
    test('provides initial state', async () => {
      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-wizard-open')).toHaveTextContent('false');
        expect(screen.getByTestId('current-step')).toHaveTextContent('1');
        expect(screen.getByTestId('repositories-count')).toHaveTextContent('0');
      });
    });

    test('loads repositories on mount', async () => {
      const mockRepos = [
        { repository_id: 'repo-1', name: 'test-repo' },
        { repository_id: 'repo-2', name: 'another-repo' },
      ];
      repositoryApi.listRepositories.mockResolvedValue(mockRepos);

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('repositories-count')).toHaveTextContent('2');
      });
    });

    test('handles repository load error', async () => {
      repositoryApi.listRepositories.mockRejectedValue(new Error('Network error'));

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Network error');
      });
    });

    test('ignores 404 errors (no repositories yet)', async () => {
      const error = new Error('Not found');
      error.status = 404;
      repositoryApi.listRepositories.mockRejectedValue(error);

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false');
        expect(screen.getByTestId('error')).toHaveTextContent('none');
      });
    });
  });

  describe('Wizard actions', () => {
    test('openWizard sets wizard state correctly', async () => {
      const user = userEvent.setup();

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await user.click(screen.getByTestId('open-wizard'));

      expect(screen.getByTestId('is-wizard-open')).toHaveTextContent('true');
      expect(screen.getByTestId('current-step')).toHaveTextContent('1');
    });

    test('closeWizard closes the wizard', async () => {
      const user = userEvent.setup();

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await user.click(screen.getByTestId('open-wizard'));
      expect(screen.getByTestId('is-wizard-open')).toHaveTextContent('true');

      await user.click(screen.getByTestId('close-wizard'));
      expect(screen.getByTestId('is-wizard-open')).toHaveTextContent('false');
    });

    test('nextStep increments current step', async () => {
      const user = userEvent.setup();

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await user.click(screen.getByTestId('open-wizard'));
      expect(screen.getByTestId('current-step')).toHaveTextContent('1');

      await user.click(screen.getByTestId('next-step'));
      expect(screen.getByTestId('current-step')).toHaveTextContent('2');

      await user.click(screen.getByTestId('next-step'));
      expect(screen.getByTestId('current-step')).toHaveTextContent('3');
    });

    test('prevStep decrements current step', async () => {
      const user = userEvent.setup();

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await user.click(screen.getByTestId('open-wizard'));
      await user.click(screen.getByTestId('next-step'));
      await user.click(screen.getByTestId('next-step'));
      expect(screen.getByTestId('current-step')).toHaveTextContent('3');

      await user.click(screen.getByTestId('prev-step'));
      expect(screen.getByTestId('current-step')).toHaveTextContent('2');
    });

    test('prevStep does not go below step 1', async () => {
      const user = userEvent.setup();

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await user.click(screen.getByTestId('open-wizard'));
      await user.click(screen.getByTestId('prev-step'));

      expect(screen.getByTestId('current-step')).toHaveTextContent('1');
    });

    test('nextStep does not exceed max step', async () => {
      const user = userEvent.setup();

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await user.click(screen.getByTestId('open-wizard'));

      // Click next many times
      for (let i = 0; i < 10; i++) {
        await user.click(screen.getByTestId('next-step'));
      }

      expect(screen.getByTestId('current-step')).toHaveTextContent(String(WizardSteps.COMPLETION));
    });

    test('selectProvider sets the provider', async () => {
      const user = userEvent.setup();

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await user.click(screen.getByTestId('select-github'));

      expect(screen.getByTestId('provider')).toHaveTextContent('github');
    });

    test('resetWizard clears all wizard state', async () => {
      const user = userEvent.setup();

      render(
        <RepositoryProvider>
          <TestConsumer />
        </RepositoryProvider>
      );

      await user.click(screen.getByTestId('open-wizard'));
      await user.click(screen.getByTestId('select-github'));
      await user.click(screen.getByTestId('next-step'));

      await user.click(screen.getByTestId('reset-wizard'));

      expect(screen.getByTestId('is-wizard-open')).toHaveTextContent('false');
      expect(screen.getByTestId('current-step')).toHaveTextContent('1');
      expect(screen.getByTestId('provider')).toHaveTextContent('none');
    });
  });

  describe('Repository selection', () => {
    test('toggleRepoSelection adds and removes repos', async () => {
      let capturedContext;

      render(
        <RepositoryProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </RepositoryProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      // Set up available repos first
      act(() => {
        capturedContext.openWizard();
      });

      // Simulate available repos being loaded
      await act(async () => {
        // Toggle selection
        capturedContext.toggleRepoSelection('repo-1');
      });

      expect(capturedContext.selectedRepos).toContain('repo-1');

      act(() => {
        capturedContext.toggleRepoSelection('repo-1');
      });

      expect(capturedContext.selectedRepos).not.toContain('repo-1');
    });
  });

  describe('WizardSteps constants', () => {
    test('exports correct step values', () => {
      expect(WizardSteps.CONNECT_PROVIDER).toBe(1);
      expect(WizardSteps.SELECT_REPOSITORIES).toBe(2);
      expect(WizardSteps.CONFIGURE_ANALYSIS).toBe(3);
      expect(WizardSteps.REVIEW).toBe(4);
      expect(WizardSteps.COMPLETION).toBe(5);
    });
  });

  describe('useRepositories', () => {
    test('throws error when used outside RepositoryProvider', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestConsumer />);
      }).toThrow('useRepositories must be used within a RepositoryProvider');

      consoleSpy.mockRestore();
    });
  });
});
