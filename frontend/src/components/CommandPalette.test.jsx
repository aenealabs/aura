import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { CommandPaletteProvider, useCommandPalette, CommandPaletteTrigger } from './CommandPalette';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Test component that uses the context
function TestComponent({ onOpen }) {
  const { open, isOpen } = useCommandPalette();
  return (
    <div>
      <button onClick={() => { open(); onOpen?.(); }}>Open Palette</button>
      <span data-testid="is-open">{isOpen ? 'open' : 'closed'}</span>
    </div>
  );
}

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock scrollIntoView which isn't available in JSDOM
    // Must be set in beforeEach to ensure it's available for each test
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  test('does not render modal when closed', () => {
    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('renders modal when opened', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  test('has search input when open', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });
  });

  test('filters results based on search query', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    // Wait for the palette to fully load with initial results
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });

    // Wait for default items to appear before typing (prevents race condition)
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /dashboard/i })).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search/i);
    await user.type(searchInput, 'sett');

    // Settings should be visible after typing "sett"
    // Use longer timeout to handle system load during full test suite
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /settings/i })).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  test('closes on escape key', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('closes on backdrop click', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Click the backdrop (the aria-hidden div)
    const backdrop = document.querySelector('[aria-hidden="true"]');
    await user.click(backdrop);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('navigates when result is selected', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });

    // Wait for default items to appear - Dashboard is in the Pages category
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /dashboard/i })).toBeInTheDocument();
    });

    // Click on Dashboard result
    const dashboardButton = screen.getByRole('option', { name: /dashboard/i });
    await user.click(dashboardButton);

    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  test('shows no results message when search has no matches', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });

    // Type a query that won't match anything
    await user.type(screen.getByPlaceholderText(/search/i), 'zzzznothing');

    await waitFor(() => {
      // The component shows "No results found for "query""
      expect(screen.getByText(/No results found/i)).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  test('shows category headers', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    await waitFor(() => {
      // Should show category like "Pages" or "Quick Actions"
      expect(screen.getByText('Pages')).toBeInTheDocument();
    });
  });

  test('shows keyboard shortcuts hint', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    await waitFor(() => {
      // Should show hints like "Enter to select" or "↑↓ to navigate"
      expect(screen.getByText(/to select/i)).toBeInTheDocument();
      expect(screen.getByText(/to navigate/i)).toBeInTheDocument();
    });
  });

  test('focuses search input when opened', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText('Open Palette'));

    await waitFor(() => {
      const searchInput = screen.getByPlaceholderText(/search/i);
      expect(document.activeElement).toBe(searchInput);
    });
  });

  test('opens with keyboard shortcut (Cmd+K)', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <TestComponent />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    // Simulate Cmd+K
    await user.keyboard('{Meta>}k{/Meta}');

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });
});

describe('CommandPaletteTrigger', () => {
  test('renders trigger button', () => {
    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <CommandPaletteTrigger />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    expect(screen.getByText(/go to/i)).toBeInTheDocument();
  });

  test('opens palette when clicked', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <CommandPaletteTrigger />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    await user.click(screen.getByText(/go to/i));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  test('shows keyboard shortcut hint', () => {
    render(
      <BrowserRouter>
        <CommandPaletteProvider>
          <CommandPaletteTrigger />
        </CommandPaletteProvider>
      </BrowserRouter>
    );

    // Should show Cmd+K or Ctrl+K
    expect(screen.getByText(/\+K/)).toBeInTheDocument();
  });
});
