/**
 * Tests for ZscalerConfig component
 * ADR-053: Enterprise Security Integrations
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import ZscalerConfig from './ZscalerConfig';

// Mock the useIntegrationConfig hook
vi.mock('../../hooks/useIntegrations', () => ({
  useIntegrationConfig: vi.fn(),
}));

import { useIntegrationConfig } from '../../hooks/useIntegrations';

const mockConfig = {
  zia_base_url: '',
  zpa_base_url: '',
  cloud: 'zscaler.net',
  api_key: '',
  client_id: '',
  client_secret: '',
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

describe('ZscalerConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook });
  });

  test('renders nothing when isOpen is false', () => {
    const { container } = render(
      <ZscalerConfig isOpen={false} onClose={vi.fn()} onSave={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders modal when isOpen is true', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Configure Zscaler Zero Trust')).toBeInTheDocument();
    expect(screen.getByText('Cloud-native security platform for zero trust architecture')).toBeInTheDocument();
  });

  test('displays GovCloud toggle', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('GovCloud Environment')).toBeInTheDocument();
    expect(screen.getByText(/Enable for US Government/)).toBeInTheDocument();
  });

  test('displays ZIA section', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('ZIA (Zscaler Internet Access)')).toBeInTheDocument();
  });

  test('displays ZPA section', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('ZPA (Zscaler Private Access)')).toBeInTheDocument();
  });

  test('displays API credentials section', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('API Credentials')).toBeInTheDocument();
  });

  test('displays cloud environment selector', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    // Multiple comboboxes exist (cloud environment and sync interval)
    const comboboxes = screen.getAllByRole('combobox');
    expect(comboboxes.length).toBeGreaterThanOrEqual(1);
  });

  test('displays feature toggles', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Enabled Features')).toBeInTheDocument();
    expect(screen.getByText('Web Security (ZIA)')).toBeInTheDocument();
    expect(screen.getByText('Private Access (ZPA)')).toBeInTheDocument();
    expect(screen.getByText('DLP Incidents')).toBeInTheDocument();
    expect(screen.getByText('URL Filtering Logs')).toBeInTheDocument();
  });

  test('displays sync settings section', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Sync Settings')).toBeInTheDocument();
  });

  test('calls updateField when API key is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const apiKeyInput = screen.getByPlaceholderText('Enter your Zscaler API key');
    await user.type(apiKeyInput, 'test-api-key');

    expect(updateField).toHaveBeenCalledWith('api_key', expect.any(String));
  });

  test('shows loading spinner when loading', () => {
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, loading: true });

    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.queryByText('API Credentials')).not.toBeInTheDocument();
  });

  test('Test Connection button is disabled when credentials are empty', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).toBeDisabled();
  });

  test('Test Connection button is enabled when required fields are filled', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      config: {
        ...mockConfig,
        zia_base_url: 'https://zsapi.zscaler.net',
        api_key: 'test-key',
        client_id: 'test-client',
        client_secret: 'test-secret',
      },
    });

    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).not.toBeDisabled();
  });

  test('shows success message when test passes', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful', latency_ms: 50 },
    });

    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection successful')).toBeInTheDocument();
  });

  test('shows error message when test fails', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: false, message: 'Invalid credentials' },
    });

    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
  });

  test('displays validation errors for zia_base_url', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        zia_base_url: 'ZIA URL is required',
      },
    });

    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('ZIA URL is required')).toBeInTheDocument();
  });

  test('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<ZscalerConfig isOpen={true} onClose={onClose} onSave={vi.fn()} />);

    await user.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  test('displays footer security message', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText(/encrypted at rest/i)).toBeInTheDocument();
  });

  test('Save button is disabled until test passes', () => {
    render(<ZscalerConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).toBeDisabled();
  });
});
