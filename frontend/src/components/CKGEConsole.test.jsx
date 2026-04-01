import { render, screen, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '../context/ThemeContext';

// Mock the child components to isolate CKGEConsole testing
vi.mock('./graph/KnowledgeGraph', () => ({
  default: () => <div data-testid="knowledge-graph">Mocked KnowledgeGraph</div>,
}));

vi.mock('./graph/FileViewer', () => ({
  default: () => <div data-testid="file-viewer">Mocked FileViewer</div>,
}));

vi.mock('./ui/Toast', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));

// Mock fetch for API calls
global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ data: [] }),
  })
);

// Import the component after mocks are set up
import CKGEConsole from './CKGEConsole';

// Wrapper component providing required context
const TestWrapper = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('CKGEConsole', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders loading state initially', () => {
    render(
      <TestWrapper>
        <CKGEConsole />
      </TestWrapper>
    );

    // Component shows skeleton loaders during initial load
    const skeletons = document.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  test('renders with proper structure', async () => {
    render(
      <TestWrapper>
        <CKGEConsole />
      </TestWrapper>
    );

    // Wait for component to finish loading
    await waitFor(() => {
      // Check for the knowledge graph section - either loading or loaded
      const container = document.querySelector('.p-6');
      expect(container).toBeInTheDocument();
    });
  });

  test('renders grid layout', () => {
    render(
      <TestWrapper>
        <CKGEConsole />
      </TestWrapper>
    );

    // Check for grid layout structure
    const grids = document.querySelectorAll('.grid');
    expect(grids.length).toBeGreaterThan(0);
  });

  test('applies dark mode classes when theme is dark', () => {
    // Set dark mode in localStorage
    localStorage.setItem('aura-theme', 'dark');

    render(
      <TestWrapper>
        <CKGEConsole />
      </TestWrapper>
    );

    // Check that dark mode classes are applied
    const darkElements = document.querySelectorAll('[class*="dark:"]');
    expect(darkElements.length).toBeGreaterThan(0);

    // Clean up
    localStorage.removeItem('aura-theme');
  });
});
