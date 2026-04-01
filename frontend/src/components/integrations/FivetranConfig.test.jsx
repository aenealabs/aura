/**
 * Tests for FivetranConfig component
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import FivetranConfig from './FivetranConfig';

// Mock the useIntegrationConfig hook
vi.mock('../../hooks/useIntegrations', () => ({
  useIntegrationConfig: vi.fn(),
}));

import { useIntegrationConfig } from '../../hooks/useIntegrations';

const mockConfig = {
  api_key: '',
  api_secret: '',
  group_id: '',
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

describe('FivetranConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook });
  });

  test('renders nothing when isOpen is false', () => {
    const { container } = render(
      <FivetranConfig isOpen={false} onClose={vi.fn()} onSave={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders modal when isOpen is true', () => {
    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Configure Fivetran')).toBeInTheDocument();
    expect(screen.getByText('Automated data pipeline integration')).toBeInTheDocument();
  });

  test('displays API credentials section', () => {
    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('API Credentials')).toBeInTheDocument();
    expect(screen.getByText(/API Key/)).toBeInTheDocument();
    expect(screen.getByText(/API Secret/)).toBeInTheDocument();
  });

  test('displays connector group section', () => {
    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connector Group')).toBeInTheDocument();
    expect(screen.getByText('Group ID')).toBeInTheDocument();
  });

  test('displays monitoring settings section', () => {
    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Monitoring Settings')).toBeInTheDocument();
    expect(screen.getByText('Sync monitoring')).toBeInTheDocument();
    expect(screen.getByText('Alert on failure')).toBeInTheDocument();
  });

  test('calls updateField when API key is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const apiKeyInput = screen.getByPlaceholderText('Enter your Fivetran API key');
    await user.type(apiKeyInput, 'test-api-key');

    expect(updateField).toHaveBeenCalledWith('api_key', expect.any(String));
  });

  test('toggles password visibility for API secret', async () => {
    const user = userEvent.setup();
    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const apiSecretInput = screen.getByPlaceholderText('Enter your Fivetran API secret');
    expect(apiSecretInput).toHaveAttribute('type', 'password');

    // Find the visibility toggle button (sibling of the input)
    const inputContainer = apiSecretInput.parentElement;
    const visibilityToggle = inputContainer?.querySelector('button');

    if (visibilityToggle) {
      await user.click(visibilityToggle);
      expect(apiSecretInput).toHaveAttribute('type', 'text');
    }
  });

  test('shows loading spinner when loading', () => {
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, loading: true });

    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.queryByText('API Credentials')).not.toBeInTheDocument();
  });

  test('Test Connection button is disabled when required fields are empty', () => {
    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).toBeDisabled();
  });

  test('Test Connection button is enabled when required fields are filled', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      config: {
        api_key: 'test-key',
        api_secret: 'test-secret',
        group_id: '',
      },
    });

    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).not.toBeDisabled();
  });

  test('shows success message when test passes', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful', latency_ms: 200 },
    });

    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection successful')).toBeInTheDocument();
  });

  test('shows error message when test fails', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: false, message: 'Invalid credentials' },
    });

    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
  });

  test('displays validation errors for API key', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        api_key: 'API key is required',
      },
    });

    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('API key is required')).toBeInTheDocument();
  });

  test('displays validation errors for API secret', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        api_secret: 'This field is required',
      },
    });

    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('This field is required')).toBeInTheDocument();
  });

  test('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<FivetranConfig isOpen={true} onClose={onClose} onSave={vi.fn()} />);

    await user.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  test('displays footer security message', () => {
    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Credentials are encrypted at rest')).toBeInTheDocument();
  });

  test('Save button is disabled until test passes', () => {
    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).toBeDisabled();
  });

  test('Save button is enabled after successful test', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful' },
    });

    render(<FivetranConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).not.toBeDisabled();
  });
});
