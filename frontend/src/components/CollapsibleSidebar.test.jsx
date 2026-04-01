import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter, useLocation } from 'react-router-dom';
import CollapsibleSidebar from './CollapsibleSidebar';

// Mock useLocation to control active route
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useLocation: vi.fn(),
  };
});

// Mock contexts
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { name: 'Test User', email: 'test@example.com', role: 'admin' },
    signOut: vi.fn(),
  }),
}));

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ isDarkMode: false, toggleTheme: vi.fn() }),
}));

vi.mock('../context/SecurityAlertsContext', () => ({
  useSecurityAlerts: () => ({
    alerts: [],
    unacknowledgedCount: 0,
    loading: false,
  }),
}));

vi.mock('../context/DeveloperModeContext', () => ({
  useDeveloperMode: () => ({
    isDeveloperMode: false,
    toggleDeveloperMode: vi.fn(),
    devSettings: {},
    updateDevSetting: vi.fn(),
  }),
}));

// Mock CommandPalette
vi.mock('./CommandPalette', () => ({
  CommandPaletteTrigger: () => <div data-testid="command-palette-trigger">Search</div>,
  useCommandPalette: () => ({ open: vi.fn(), close: vi.fn(), isOpen: false }),
}));

// Mock UserMenu
vi.mock('./UserMenu', () => ({
  default: ({ collapsed }) => (
    <div data-testid="user-menu">
      {!collapsed && <span>Test User</span>}
    </div>
  ),
}));

describe('CollapsibleSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useLocation.mockReturnValue({ pathname: '/' });
    localStorage.clear();
  });

  test('renders sidebar with navigation links', () => {
    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    // Check for navigation items
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  test('has section headers', () => {
    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    // Actual section headers in the component
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Security')).toBeInTheDocument();
    expect(screen.getByText('Intelligence')).toBeInTheDocument();
  });

  test('collapses and expands on toggle', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    const toggleButton = screen.getByRole('button', { name: /collapse sidebar/i });

    // Initially expanded
    expect(screen.getByText('Dashboard')).toBeVisible();

    // Click to collapse
    await user.click(toggleButton);

    // Toggle button label should change
    expect(screen.getByRole('button', { name: /expand sidebar/i })).toBeInTheDocument();
  });

  test('shows user menu section', () => {
    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    expect(screen.getByTestId('user-menu')).toBeInTheDocument();
  });

  test('has navigation element', () => {
    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    const nav = screen.getByRole('navigation');
    expect(nav).toBeInTheDocument();
  });

  test('shows badge for approvals', () => {
    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    // Should show approval badge with count
    expect(screen.getByText('7')).toBeInTheDocument();
  });

  test('shows multiple badges with notification counts', () => {
    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    // Should show badges - there are multiple "2" badges (Incidents and Mission Control)
    const twoBadges = screen.getAllByText('2');
    expect(twoBadges.length).toBeGreaterThanOrEqual(1);
  });

  test('persists expanded state to localStorage', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    const toggleButton = screen.getByRole('button', { name: /collapse sidebar/i });
    await user.click(toggleButton);

    // Should save to localStorage with correct key
    const savedState = localStorage.getItem('sidebarExpanded');
    expect(savedState).toBe('false');
  });

  test('shows New Project button', () => {
    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    expect(screen.getByText('New Project')).toBeInTheDocument();
  });

  test('shows dark mode toggle', () => {
    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    expect(screen.getByText('Theme')).toBeInTheDocument();
  });

  test('renders all main navigation links', () => {
    render(
      <BrowserRouter>
        <CollapsibleSidebar />
      </BrowserRouter>
    );

    // Overview section
    expect(screen.getByText('Repositories')).toBeInTheDocument();
    expect(screen.getByText('Environments')).toBeInTheDocument();

    // Security section
    expect(screen.getByText('Approvals')).toBeInTheDocument();
    expect(screen.getByText('Incidents')).toBeInTheDocument();
    expect(screen.getByText('Red Team')).toBeInTheDocument();
    expect(screen.getByText('Alerts')).toBeInTheDocument();

    // Intelligence section
    expect(screen.getByText('Knowledge Graph')).toBeInTheDocument();
    expect(screen.getByText('Agents')).toBeInTheDocument();
    expect(screen.getByText('Mission Control')).toBeInTheDocument();
  });
});
