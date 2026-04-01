/**
 * Project Aura - DiagramGitDialog Tests (ADR-060 Phase 4)
 *
 * Tests for GitHub/GitLab commit dialog component.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';

// Mock ThemeContext
vi.mock('../../context/ThemeContext', () => ({
  useTheme: () => ({ isDarkMode: false, toggleTheme: vi.fn() }),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

import DiagramGitDialog, {
  RepositorySelector,
  CommitForm,
  CommitResult,
} from './DiagramGitDialog';

const SAMPLE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>';

const MOCK_CONNECTIONS = [
  {
    connectionId: 'conn-1',
    provider: 'github',
    providerUsername: 'testuser',
  },
  {
    connectionId: 'conn-2',
    provider: 'gitlab',
    providerUsername: 'gitlabuser',
  },
];

const MOCK_REPOSITORIES = [
  { fullName: 'testuser/repo1', name: 'repo1' },
  { fullName: 'testuser/repo2', name: 'repo2' },
];

describe('DiagramGitDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  describe('Dialog Behavior', () => {
    test('renders when isOpen is true', () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ connections: [] }),
      });

      render(
        <DiagramGitDialog
          isOpen={true}
          onClose={vi.fn()}
          diagramContent={SAMPLE_SVG}
        />
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Commit to Repository')).toBeInTheDocument();
    });

    test('does not render when isOpen is false', () => {
      render(
        <DiagramGitDialog
          isOpen={false}
          onClose={vi.fn()}
          diagramContent={SAMPLE_SVG}
        />
      );

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    test('calls onClose when close button clicked', async () => {
      const onClose = vi.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ connections: [] }),
      });

      render(
        <DiagramGitDialog
          isOpen={true}
          onClose={onClose}
          diagramContent={SAMPLE_SVG}
        />
      );

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /close/i }));

      expect(onClose).toHaveBeenCalled();
    });

    test('calls onClose when Escape pressed', async () => {
      const onClose = vi.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ connections: [] }),
      });

      render(
        <DiagramGitDialog
          isOpen={true}
          onClose={onClose}
          diagramContent={SAMPLE_SVG}
        />
      );

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('Connection Loading', () => {
    test('fetches connections on open', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ connections: MOCK_CONNECTIONS }),
      });

      render(
        <DiagramGitDialog
          isOpen={true}
          onClose={vi.fn()}
          diagramContent={SAMPLE_SVG}
        />
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/v1/oauth/connections');
      });
    });

    test('displays connections after loading', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ connections: MOCK_CONNECTIONS }),
      });

      render(
        <DiagramGitDialog
          isOpen={true}
          onClose={vi.fn()}
          diagramContent={SAMPLE_SVG}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('testuser')).toBeInTheDocument();
      });
    });

    test('shows message when no connections configured', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ connections: [] }),
      });

      render(
        <DiagramGitDialog
          isOpen={true}
          onClose={vi.fn()}
          diagramContent={SAMPLE_SVG}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/no git connections configured/i)).toBeInTheDocument();
      });
    });
  });

  describe('Commit Button', () => {
    test('commit button is disabled without connection selected', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ connections: MOCK_CONNECTIONS }),
      });

      render(
        <DiagramGitDialog
          isOpen={true}
          onClose={vi.fn()}
          diagramContent={SAMPLE_SVG}
        />
      );

      await waitFor(() => {
        const commitButton = screen.getByRole('button', { name: /commit/i });
        expect(commitButton).toBeDisabled();
      });
    });
  });
});

describe('RepositorySelector', () => {
  const defaultProps = {
    connections: MOCK_CONNECTIONS,
    selectedConnection: null,
    onSelectConnection: vi.fn(),
    repositories: [],
    selectedRepository: null,
    onSelectRepository: vi.fn(),
    isLoading: false,
    onRefresh: vi.fn(),
  };

  test('renders connection options', () => {
    render(<RepositorySelector {...defaultProps} />);

    expect(screen.getByText('testuser')).toBeInTheDocument();
    expect(screen.getByText('gitlabuser')).toBeInTheDocument();
  });

  test('calls onSelectConnection when connection clicked', async () => {
    const onSelectConnection = vi.fn();
    render(
      <RepositorySelector {...defaultProps} onSelectConnection={onSelectConnection} />
    );

    const user = userEvent.setup();
    await user.click(screen.getByText('testuser'));

    expect(onSelectConnection).toHaveBeenCalledWith(MOCK_CONNECTIONS[0]);
  });

  test('shows repository dropdown when connection selected', () => {
    render(
      <RepositorySelector
        {...defaultProps}
        selectedConnection={MOCK_CONNECTIONS[0]}
        repositories={MOCK_REPOSITORIES}
      />
    );

    expect(screen.getByText('Repository')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  test('shows loading state during repository fetch', () => {
    render(
      <RepositorySelector
        {...defaultProps}
        selectedConnection={MOCK_CONNECTIONS[0]}
        isLoading={true}
      />
    );

    const select = screen.getByRole('combobox');
    expect(select).toBeDisabled();
  });
});

describe('CommitForm', () => {
  const defaultProps = {
    filePath: 'docs/diagram.svg',
    onFilePathChange: vi.fn(),
    commitMessage: 'Add diagram',
    onCommitMessageChange: vi.fn(),
    branch: 'main',
    onBranchChange: vi.fn(),
    createPr: false,
    onCreatePrChange: vi.fn(),
    prTitle: '',
    onPrTitleChange: vi.fn(),
    prDescription: '',
    onPrDescriptionChange: vi.fn(),
  };

  test('renders file path input', () => {
    render(<CommitForm {...defaultProps} />);

    const input = screen.getByPlaceholderText(/docs\/diagrams/i);
    expect(input).toHaveValue('docs/diagram.svg');
  });

  test('renders branch input', () => {
    render(<CommitForm {...defaultProps} />);

    const input = screen.getByPlaceholderText('main');
    expect(input).toHaveValue('main');
  });

  test('renders commit message textarea', () => {
    render(<CommitForm {...defaultProps} />);

    const textarea = screen.getByPlaceholderText(/add.*diagram/i);
    expect(textarea).toHaveValue('Add diagram');
  });

  test('shows PR fields when createPr is true', () => {
    render(<CommitForm {...defaultProps} createPr={true} />);

    expect(screen.getByText('PR Title')).toBeInTheDocument();
    expect(screen.getByText('PR Description')).toBeInTheDocument();
  });

  test('hides PR fields when createPr is false', () => {
    render(<CommitForm {...defaultProps} createPr={false} />);

    expect(screen.queryByText('PR Title')).not.toBeInTheDocument();
    expect(screen.queryByText('PR Description')).not.toBeInTheDocument();
  });

  test('toggles createPr when switch clicked', async () => {
    const onCreatePrChange = vi.fn();
    render(<CommitForm {...defaultProps} onCreatePrChange={onCreatePrChange} />);

    const user = userEvent.setup();
    const switchEl = screen.getByRole('switch');
    await user.click(switchEl);

    expect(onCreatePrChange).toHaveBeenCalledWith(true);
  });
});

describe('CommitResult', () => {
  test('renders success state', () => {
    const result = {
      success: true,
      commitSha: 'abc123def456',
      commitUrl: 'https://github.com/user/repo/commit/abc123',
      fileUrl: 'https://github.com/user/repo/blob/main/diagram.svg',
    };

    render(<CommitResult result={result} onClose={vi.fn()} />);

    expect(screen.getByText(/committed successfully/i)).toBeInTheDocument();
    expect(screen.getByText('abc123d')).toBeInTheDocument();
    expect(screen.getByText('View file')).toBeInTheDocument();
  });

  test('renders PR link when present', () => {
    const result = {
      success: true,
      commitSha: 'abc123',
      prNumber: 42,
      prUrl: 'https://github.com/user/repo/pull/42',
    };

    render(<CommitResult result={result} onClose={vi.fn()} />);

    expect(screen.getByText(/pull request #42/i)).toBeInTheDocument();
  });

  test('renders error state', () => {
    const result = {
      success: false,
      error: 'Authentication failed',
    };

    render(<CommitResult result={result} onClose={vi.fn()} />);

    expect(screen.getByText(/commit failed/i)).toBeInTheDocument();
    expect(screen.getByText('Authentication failed')).toBeInTheDocument();
  });

  test('returns null when result is null', () => {
    const { container } = render(<CommitResult result={null} onClose={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});
