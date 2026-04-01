/**
 * Tests for SaviyntConfig component
 * ADR-053: Enterprise Security Integrations
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import SaviyntConfig from './SaviyntConfig';

// Mock the useIntegrationConfig hook
vi.mock('../../hooks/useIntegrations', () => ({
  useIntegrationConfig: vi.fn(),
}));

import { useIntegrationConfig } from '../../hooks/useIntegrations';

const mockConfig = {
  base_url: '',
  username: '',
  password: '',
};

const defaultMockHook = {
  config: mockConfig,
  loading: false,
  saving: false,
  testing: false,
  testResult: null,
  validationErrors: {},
  updateField: vi.fn(),
  testConnection: vi.fn(),
  saveConfig: vi.fn(),
};

describe('SaviyntConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook });
  });

  test('renders nothing when isOpen is false', () => {
    const { container } = render(
      <SaviyntConfig isOpen={false} onClose={vi.fn()} onSave={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders modal when isOpen is true', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Configure Saviynt Enterprise Identity Cloud')).toBeInTheDocument();
  });

  test('displays GovCloud toggle', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('GovCloud Environment')).toBeInTheDocument();
  });

  test('displays connection settings section', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection Settings')).toBeInTheDocument();
  });

  test('displays base URL field', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByPlaceholderText('https://your-tenant.saviyntcloud.com')).toBeInTheDocument();
  });

  test('displays username field', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByPlaceholderText('api_service_account')).toBeInTheDocument();
  });

  test('displays feature toggles for identity governance', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Enabled Features')).toBeInTheDocument();
    expect(screen.getByText('User Management')).toBeInTheDocument();
    expect(screen.getByText('Entitlements')).toBeInTheDocument();
    expect(screen.getByText('Access Requests')).toBeInTheDocument();
    expect(screen.getByText('Certifications')).toBeInTheDocument();
  });

  test('displays PAM and risk analytics features', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('PAM Sessions')).toBeInTheDocument();
    expect(screen.getByText('Risk Analytics')).toBeInTheDocument();
  });

  test('displays sync settings section', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Sync Settings')).toBeInTheDocument();
  });

  test('calls updateField when username is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const usernameInput = screen.getByPlaceholderText('api_service_account');
    await user.type(usernameInput, 'test-user');

    expect(updateField).toHaveBeenCalledWith('username', expect.any(String));
  });

  test('calls updateField when base URL is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const urlInput = screen.getByPlaceholderText('https://your-tenant.saviyntcloud.com');
    await user.type(urlInput, 'https://test.saviyntcloud.com');

    expect(updateField).toHaveBeenCalledWith('base_url', expect.any(String));
  });

  test('shows loading spinner when loading', () => {
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, loading: true });

    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.queryByText('Connection Settings')).not.toBeInTheDocument();
  });

  test('Test Connection button is disabled when credentials are empty', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).toBeDisabled();
  });

  test('Test Connection button is enabled when credentials are filled', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      config: {
        base_url: 'https://test.saviyntcloud.com',
        username: 'test-user',
        password: 'mock-credential-for-test',
      },
    });

    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).not.toBeDisabled();
  });

  test('shows success message when test passes', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful', latency_ms: 45 },
    });

    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection successful')).toBeInTheDocument();
  });

  test('shows error message when test fails', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: false, message: 'Authentication failed' },
    });

    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Authentication failed')).toBeInTheDocument();
  });

  test('displays validation errors', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        base_url: 'Base URL is required',
      },
    });

    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Base URL is required')).toBeInTheDocument();
  });

  test('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<SaviyntConfig isOpen={true} onClose={onClose} onSave={vi.fn()} />);

    await user.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  test('displays footer security message', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText(/encrypted at rest/i)).toBeInTheDocument();
  });

  test('Save button is disabled until test passes', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).toBeDisabled();
  });

  test('risk analytics settings section is hidden by default', () => {
    render(<SaviyntConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    // Risk Analytics Settings section only appears when risk_analytics feature is enabled
    expect(screen.queryByText('Risk Analytics Settings')).not.toBeInTheDocument();
  });
});
