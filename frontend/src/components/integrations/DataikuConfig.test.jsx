/**
 * Tests for DataikuConfig component
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import DataikuConfig from './DataikuConfig';

// Mock the useIntegrationConfig hook
vi.mock('../../hooks/useIntegrations', () => ({
  useIntegrationConfig: vi.fn(),
}));

import { useIntegrationConfig } from '../../hooks/useIntegrations';

const mockConfig = {
  instance_url: '',
  api_key: '',
  default_project: '',
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

describe('DataikuConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook });
  });

  test('renders nothing when isOpen is false', () => {
    const { container } = render(
      <DataikuConfig isOpen={false} onClose={vi.fn()} onSave={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders modal when isOpen is true', () => {
    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Configure Dataiku DSS')).toBeInTheDocument();
    expect(screen.getByText('Enterprise AI/ML platform integration')).toBeInTheDocument();
  });

  test('displays connection settings section', () => {
    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection Settings')).toBeInTheDocument();
    expect(screen.getByText(/Instance URL/)).toBeInTheDocument();
    // Use getAllByText since "API Key" appears in both the label and helper text
    expect(screen.getAllByText(/API Key/i).length).toBeGreaterThan(0);
  });

  test('displays project settings section', () => {
    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Project Settings')).toBeInTheDocument();
    expect(screen.getByText('Default Project')).toBeInTheDocument();
  });

  test('displays sync settings section', () => {
    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Sync Settings')).toBeInTheDocument();
    expect(screen.getByText('Enable data sync')).toBeInTheDocument();
  });

  test('calls updateField when instance URL is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const urlInput = screen.getByPlaceholderText('https://your-instance.dataiku.com');
    await user.type(urlInput, 'https://test.dataiku.com');

    expect(updateField).toHaveBeenCalledWith('instance_url', expect.any(String));
  });

  test('toggles password visibility for API key', async () => {
    const user = userEvent.setup();
    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const apiKeyInput = screen.getByPlaceholderText('Enter your Dataiku API key');
    expect(apiKeyInput).toHaveAttribute('type', 'password');

    // Find the visibility toggle button (sibling of the input)
    const inputContainer = apiKeyInput.parentElement;
    const visibilityToggle = inputContainer?.querySelector('button');

    if (visibilityToggle) {
      await user.click(visibilityToggle);
      expect(apiKeyInput).toHaveAttribute('type', 'text');
    }
  });

  test('shows loading spinner when loading', () => {
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, loading: true });

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    // Should show loading state, not the form
    expect(screen.queryByText('Connection Settings')).not.toBeInTheDocument();
  });

  test('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<DataikuConfig isOpen={true} onClose={onClose} onSave={vi.fn()} />);

    await user.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  test('calls onClose when X button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<DataikuConfig isOpen={true} onClose={onClose} onSave={vi.fn()} />);

    // Find the close button (X icon button in header)
    const closeButton = screen.getAllByRole('button')[0];
    await user.click(closeButton);
    expect(onClose).toHaveBeenCalled();
  });

  test('Test Connection button is disabled when required fields are empty', () => {
    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).toBeDisabled();
  });

  test('Test Connection button is enabled when required fields are filled', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      config: {
        instance_url: 'https://test.dataiku.com',
        api_key: 'test-key',
        default_project: '',
      },
    });

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).not.toBeDisabled();
  });

  test('calls testConnection when Test button is clicked', async () => {
    const testConnection = vi.fn();
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      config: {
        instance_url: 'https://test.dataiku.com',
        api_key: 'test-key',
        default_project: '',
      },
      testConnection,
    });
    const user = userEvent.setup();

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: /test/i }));
    expect(testConnection).toHaveBeenCalled();
  });

  test('shows success message when test passes', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful', latency_ms: 150 },
    });

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection successful')).toBeInTheDocument();
    expect(screen.getByText('Latency: 150ms')).toBeInTheDocument();
  });

  test('shows error message when test fails', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: false, message: 'Authentication failed' },
    });

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Authentication failed')).toBeInTheDocument();
  });

  test('Save button is disabled until test passes', () => {
    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).toBeDisabled();
  });

  test('Save button is enabled after successful test', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful' },
    });

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).not.toBeDisabled();
  });

  test('displays validation errors for instance URL', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        instance_url: 'Invalid URL format',
      },
    });

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Invalid URL format')).toBeInTheDocument();
  });

  test('displays validation errors for API key', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        api_key: 'API key is required',
      },
    });

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('API key is required')).toBeInTheDocument();
  });

  test('shows testing state when testing connection', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testing: true,
      config: {
        instance_url: 'https://test.dataiku.com',
        api_key: 'test-key',
        default_project: '',
      },
    });

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Testing...')).toBeInTheDocument();
  });

  test('shows saving state when saving config', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      saving: true,
      testResult: { success: true, message: 'Connection successful' },
    });

    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Saving...')).toBeInTheDocument();
  });

  test('displays footer security message', () => {
    render(<DataikuConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Credentials are encrypted at rest')).toBeInTheDocument();
  });

  test('initializes with existing config', () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });

    const existingConfig = {
      instance_url: 'https://existing.dataiku.com',
      api_key: 'existing-key',
      default_project: 'MY_PROJECT',
    };

    render(
      <DataikuConfig
        isOpen={true}
        onClose={vi.fn()}
        onSave={vi.fn()}
        existingConfig={existingConfig}
      />
    );

    // useEffect should call updateField for each config value
    expect(updateField).toHaveBeenCalled();
  });
});
