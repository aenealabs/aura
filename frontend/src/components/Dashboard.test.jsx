import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import Dashboard from './Dashboard';

// Mock child components
vi.mock('./ui/LoadingSkeleton', () => ({
  PageSkeleton: () => <div data-testid="page-skeleton">Loading...</div>,
  SkeletonDashboard: () => <div data-testid="skeleton-dashboard">Loading...</div>,
}));

vi.mock('./ui/Charts', () => ({
  LineChart: () => <div data-testid="line-chart">Line Chart</div>,
  DonutChart: () => <div data-testid="donut-chart">Donut Chart</div>,
  ProgressChart: () => <div data-testid="progress-chart">Progress Chart</div>,
}));

vi.mock('./ui/MetricCard', () => ({
  default: ({ title }) => <div data-testid="metric-card">{title}</div>,
}));

vi.mock('./ui/ActivityFeed', () => ({
  default: () => <div data-testid="activity-feed">Activity Feed</div>,
}));

vi.mock('./ui/DashboardGrid', () => ({
  default: ({ renderWidget }) => (
    <div data-testid="dashboard-grid">
      {renderWidget('active-agents')}
      {renderWidget('vulnerabilities')}
    </div>
  ),
}));

vi.mock('./ui/Toast', () => ({
  useToast: () => ({
    toast: { success: vi.fn(), error: vi.fn() },
  }),
}));

vi.mock('./modals', () => ({
  ScanModal: ({ isOpen }) => isOpen ? <div data-testid="scan-modal">Scan Modal</div> : null,
  HealthCheckModal: ({ isOpen }) => isOpen ? <div data-testid="health-check-modal">Health Check Modal</div> : null,
}));

vi.mock('./CommandPalette', () => ({
  DashboardSearchTrigger: () => <div data-testid="search-trigger">Search</div>,
  useCommandPalette: () => ({ open: vi.fn() }),
}));

// Mock context providers
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { name: 'Test User', email: 'test@example.com' },
    isAuthenticated: true,
  }),
}));

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ isDarkMode: false }),
}));

vi.mock('../context/SecurityAlertsContext', () => ({
  useSecurityAlerts: () => ({
    alerts: [],
    unacknowledgedCount: 0,
    loading: false,
  }),
}));

// Mock the useDashboardData hook
vi.mock('../hooks/useDashboardData', () => ({
  useDashboardData: vi.fn(),
}));

import { useDashboardData } from '../hooks/useDashboardData';

const mockDashboardData = {
  summary: {
    agents: { active: 5, trend: 10, sparkline: [] },
    approvals: { pending: 7, trend: -5 },
    vulnerabilities: { open: 24, trend: -15, sparkline: [], history: [], severity: { critical: 3, high: 8, medium: 9, low: 4 } },
    patches: { deployed: 156, trend: 20, sparkline: [] },
    sandbox: { running: 3, status: 'healthy' },
    anomalies: { count: 2 },
  },
  agents: [
    { id: 'agent-1', name: 'Coder Agent', status: 'active', task: 'Reviewing code', progress: 75 },
  ],
  health: {
    api: { percentage: 96 },
    graphRag: { percentage: 82, nodes: 12847, edges: 38291, queries24h: 1243, avgLatencyMs: 42 },
    llm: { quotaUsed: 45 },
    sandbox: { available: 3 },
  },
  scans: [],
};

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('shows loading skeleton while data is loading', () => {
    useDashboardData.mockReturnValue({
      data: {},
      loading: { summary: true, agents: true, health: true, scans: true },
      error: {},
      isInitialLoading: true,
      refetch: vi.fn(),
      refetchSection: vi.fn(),
      lastUpdated: null,
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    expect(screen.getByTestId('page-skeleton')).toBeInTheDocument();
  });

  test('renders dashboard header', async () => {
    useDashboardData.mockReturnValue({
      data: mockDashboardData,
      loading: { summary: false, agents: false, health: false, scans: false },
      error: {},
      isInitialLoading: false,
      refetch: vi.fn(),
      refetchSection: vi.fn(),
      lastUpdated: new Date().toISOString(),
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    expect(screen.getByText('Security Dashboard')).toBeInTheDocument();
    expect(screen.getByText(/real-time overview/i)).toBeInTheDocument();
  });

  test('displays quick action buttons', async () => {
    useDashboardData.mockReturnValue({
      data: mockDashboardData,
      loading: { summary: false, agents: false, health: false, scans: false },
      error: {},
      isInitialLoading: false,
      refetch: vi.fn(),
      refetchSection: vi.fn(),
      lastUpdated: null,
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    expect(screen.getByText('Start Scan')).toBeInTheDocument();
    expect(screen.getByText('Review Approvals')).toBeInTheDocument();
    expect(screen.getByText('Health Check')).toBeInTheDocument();
  });

  test('refresh button triggers data reload', async () => {
    const user = userEvent.setup();
    const refetchMock = vi.fn().mockResolvedValue(undefined);

    useDashboardData.mockReturnValue({
      data: mockDashboardData,
      loading: { summary: false, agents: false, health: false, scans: false },
      error: {},
      isInitialLoading: false,
      refetch: refetchMock,
      refetchSection: vi.fn(),
      lastUpdated: null,
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    expect(refetchMock).toHaveBeenCalled();
  });

  test('renders dashboard grid', async () => {
    useDashboardData.mockReturnValue({
      data: mockDashboardData,
      loading: { summary: false, agents: false, health: false, scans: false },
      error: {},
      isInitialLoading: false,
      refetch: vi.fn(),
      refetchSection: vi.fn(),
      lastUpdated: null,
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    expect(screen.getByTestId('dashboard-grid')).toBeInTheDocument();
  });

  test('renders metric cards', async () => {
    useDashboardData.mockReturnValue({
      data: mockDashboardData,
      loading: { summary: false, agents: false, health: false, scans: false },
      error: {},
      isInitialLoading: false,
      refetch: vi.fn(),
      refetchSection: vi.fn(),
      lastUpdated: null,
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    // Check for metric cards rendered by the grid
    expect(screen.getAllByTestId('metric-card').length).toBeGreaterThan(0);
  });

  test('renders search trigger', async () => {
    useDashboardData.mockReturnValue({
      data: mockDashboardData,
      loading: { summary: false, agents: false, health: false, scans: false },
      error: {},
      isInitialLoading: false,
      refetch: vi.fn(),
      refetchSection: vi.fn(),
      lastUpdated: null,
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    expect(screen.getByTestId('search-trigger')).toBeInTheDocument();
  });

  test('opens scan modal when Start Scan is clicked', async () => {
    const user = userEvent.setup();

    useDashboardData.mockReturnValue({
      data: mockDashboardData,
      loading: { summary: false, agents: false, health: false, scans: false },
      error: {},
      isInitialLoading: false,
      refetch: vi.fn(),
      refetchSection: vi.fn(),
      lastUpdated: null,
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    // Find and click all "Start Scan" buttons (there are two - in header and widget)
    const startScanButtons = screen.getAllByText('Start Scan');
    await user.click(startScanButtons[0]);

    expect(screen.getByTestId('scan-modal')).toBeInTheDocument();
  });

  test('opens health check modal when Health Check is clicked', async () => {
    const user = userEvent.setup();

    useDashboardData.mockReturnValue({
      data: mockDashboardData,
      loading: { summary: false, agents: false, health: false, scans: false },
      error: {},
      isInitialLoading: false,
      refetch: vi.fn(),
      refetchSection: vi.fn(),
      lastUpdated: null,
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    // Find and click all "Health Check" buttons
    const healthCheckButtons = screen.getAllByText('Health Check');
    await user.click(healthCheckButtons[0]);

    expect(screen.getByTestId('health-check-modal')).toBeInTheDocument();
  });
});
