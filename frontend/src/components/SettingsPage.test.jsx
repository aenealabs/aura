import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import SettingsPage from './SettingsPage';

// Mock Toast
vi.mock('./ui/Toast', () => ({
  useToast: () => ({
    toast: {
      success: vi.fn(),
      error: vi.fn(),
    },
  }),
}));

// Mock ConfirmDialog
vi.mock('./ui/ConfirmDialog', () => ({
  useConfirm: () => ({
    confirm: vi.fn().mockResolvedValue(true),
  }),
}));

// Mock context providers
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { name: 'Test User', email: 'test@example.com', role: 'admin' },
    isAuthenticated: true,
    changePassword: vi.fn(),
  }),
}));

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ isDarkMode: false, toggleTheme: vi.fn() }),
}));

// Mock settings sub-components
vi.mock('./ComplianceSettings', () => ({
  default: () => <div data-testid="compliance-settings">Compliance Settings</div>,
}));

vi.mock('./settings/AutonomyPoliciesTab', () => ({
  default: () => <div data-testid="autonomy-settings">Autonomy Settings</div>,
}));

vi.mock('./settings/OrchestratorModeTab', () => ({
  default: () => <div data-testid="orchestrator-settings">Orchestrator Settings</div>,
}));

vi.mock('./settings/ModelRouterSettings', () => ({
  default: () => <div data-testid="model-router-settings">Model Router Settings</div>,
}));

vi.mock('./settings/NotificationsSettings', () => ({
  default: () => <div data-testid="notifications-settings">Notifications Settings</div>,
}));

vi.mock('./settings/RateLimitingSettings', () => ({
  default: () => <div data-testid="rate-limiting-settings">Rate Limiting Settings</div>,
}));

vi.mock('./settings/SecurityAlertSettings', () => ({
  default: () => <div data-testid="security-alert-settings">Security Alert Settings</div>,
}));

vi.mock('./settings/TicketingSettings', () => ({
  default: () => <div data-testid="ticketing-settings">Ticketing Settings</div>,
}));

// Mock settings API
vi.mock('../services/settingsApi', () => ({
  getSettings: vi.fn(),
  updateIntegrationMode: vi.fn(),
  updateHitlSettings: vi.fn(),
  updateMcpSettings: vi.fn(),
  updateSecuritySettings: vi.fn(),
  getAvailableExternalTools: vi.fn(),
  getMcpUsageStats: vi.fn(),
  testMcpConnection: vi.fn(),
  applyComplianceProfile: vi.fn(),
  IntegrationModes: {
    DEFENSE: 'defense',
    ENTERPRISE: 'enterprise',
    HYBRID: 'hybrid',
  },
  DEFAULT_SETTINGS: {
    integrationMode: 'enterprise',
    hitlSettings: {
      requireApprovalForPatches: true,
      requireApprovalForDeployments: true,
    },
    mcpSettings: {
      enabled: true,
      gatewayUrl: '',
      apiKey: '',
    },
    securitySettings: {
      retainLogsForDays: 90,
      blockExternalNetwork: true,
      auditAllActions: true,
    },
  },
  LOG_RETENTION_OPTIONS: [
    { value: 30, label: '30 Days', compliance: 'Basic' },
    { value: 90, label: '90 Days', compliance: 'CMMC L2 Compliant', recommended: true },
    { value: 365, label: '1 Year', compliance: 'GovCloud Ready' },
  ],
}));

import * as settingsApi from '../services/settingsApi';

describe('SettingsPage', () => {
  const mockSettings = {
    integrationMode: 'enterprise',
    hitlSettings: {
      requireApprovalForPatches: true,
      requireApprovalForDeployments: true,
      autoApproveMinorPatches: false,
      approvalTimeoutHours: 24,
      minApprovers: 1,
      notifyOnApprovalRequest: true,
      notifyOnApprovalTimeout: true,
    },
    mcpSettings: {
      enabled: true,
      gatewayUrl: 'https://gateway.example.com',
      apiKey: 'test-key',
      monthlyBudgetUsd: 100,
      dailyLimitUsd: 10,
      externalToolsEnabled: [],
    },
    securitySettings: {
      retainLogsForDays: 90,
      blockExternalNetwork: true,
      auditAllActions: true,
      sandboxIsolationLevel: 'container',
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    settingsApi.getSettings.mockResolvedValue(mockSettings);
    settingsApi.getAvailableExternalTools.mockResolvedValue([]);
    settingsApi.getMcpUsageStats.mockResolvedValue({ currentMonthCost: 0, budgetRemaining: 100 });
  });

  test('renders settings page header', async () => {
    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Platform Settings')).toBeInTheDocument();
    });
  });

  test('shows loading state while fetching settings', () => {
    settingsApi.getSettings.mockImplementation(() => new Promise(() => {}));

    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/loading settings/i)).toBeInTheDocument();
  });

  test('displays integration mode tab by default', async () => {
    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Platform Settings')).toBeInTheDocument();
    });

    // Should show integration mode options - getAllByText because each mode appears multiple times
    await waitFor(() => {
      expect(screen.getAllByText('Defense Mode').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Enterprise Mode').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Hybrid Mode').length).toBeGreaterThan(0);
    });
  });

  test('displays current mode banner', async () => {
    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      // The banner shows "Current Mode:" label
      expect(screen.getByText(/Current Mode:/i)).toBeInTheDocument();
    });
  });

  test('has navigation sidebar with tabs', async () => {
    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      // The page header should be visible
      expect(screen.getByText('Platform Settings')).toBeInTheDocument();
    });

    // Navigation is visible in mobile trigger (shows current tab)
    // and desktop sidebar. Check that nav elements exist.
    await waitFor(() => {
      // Should have navigation with settings categories
      const nav = screen.getAllByRole('navigation', { name: /settings navigation/i });
      expect(nav.length).toBeGreaterThan(0);
    });
  });

  test('switches to HITL tab on click', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('HITL Settings')).toBeInTheDocument();
    });

    await user.click(screen.getByText('HITL Settings'));

    await waitFor(() => {
      expect(screen.getByText('Approval Requirements')).toBeInTheDocument();
    });
  });

  test('switches to security policies tab on click', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      // Find the Security Policies button in the sidebar
      const securityButtons = screen.getAllByText('Security Policies');
      expect(securityButtons.length).toBeGreaterThan(0);
    });

    // Click on Security Policies tab in sidebar
    const securityButtons = screen.getAllByText('Security Policies');
    await user.click(securityButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Log Retention Policy')).toBeInTheDocument();
    });
  });

  test('has refresh button', async () => {
    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  test('refresh button triggers data reload', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });

    // Clear the initial calls
    vi.clearAllMocks();

    await user.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => {
      expect(settingsApi.getSettings).toHaveBeenCalled();
    });
  });

  test('handles settings fetch error gracefully', async () => {
    settingsApi.getSettings.mockRejectedValue(new Error('Failed to load'));

    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      // Should show error message but still render the page
      expect(screen.getByText(/failed to load settings/i)).toBeInTheDocument();
    });
  });

  test('shows MCP configuration when tab is selected', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('MCP Configuration')).toBeInTheDocument();
    });

    await user.click(screen.getByText('MCP Configuration'));

    await waitFor(() => {
      expect(screen.getByText('AgentCore Gateway')).toBeInTheDocument();
    });
  });

  test('shows compliance tab when clicked', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Compliance')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Compliance'));

    await waitFor(() => {
      expect(screen.getByTestId('compliance-settings')).toBeInTheDocument();
    });
  });
});
