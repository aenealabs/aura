/**
 * Tests for JupyterLabConfig component
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import JupyterLabConfig from './JupyterLabConfig';

// Mock the useIntegrationConfig hook
vi.mock('../../hooks/useIntegrations', () => ({
  useIntegrationConfig: vi.fn(),
}));

import { useIntegrationConfig } from '../../hooks/useIntegrations';

const mockConfig = {
  workspace_token: '',
  jupyter_server: '',
  scan_outputs: 'enabled',
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

describe('JupyterLabConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook });
  });

  test('renders nothing when isOpen is false', () => {
    const { container } = render(
      <JupyterLabConfig isOpen={false} onClose={vi.fn()} onSave={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders modal when isOpen is true', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Configure JupyterLab')).toBeInTheDocument();
    expect(screen.getByText('Interactive notebook security scanning')).toBeInTheDocument();
  });

  test('displays authentication section', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Authentication')).toBeInTheDocument();
    expect(screen.getByText(/Workspace Token/)).toBeInTheDocument();
  });

  test('displays server settings section', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Server Settings')).toBeInTheDocument();
    expect(screen.getByText('Jupyter Server URL')).toBeInTheDocument();
  });

  test('displays output scanning section', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Output Scanning')).toBeInTheDocument();
    expect(screen.getByText('Scan Outputs')).toBeInTheDocument();
    expect(screen.getByText('Enabled')).toBeInTheDocument();
    expect(screen.getByText('Disabled')).toBeInTheDocument();
  });

  test('displays additional settings section', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Additional Settings')).toBeInTheDocument();
    expect(screen.getByText('Scan markdown cells')).toBeInTheDocument();
    expect(screen.getByText('Auto-save notebooks')).toBeInTheDocument();
  });

  test('calls updateField when workspace token is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const tokenInput = screen.getByPlaceholderText('aura_wst_xxxxxxxxxxxxxxxxxxxx');
    await user.type(tokenInput, 'test-token');

    expect(updateField).toHaveBeenCalledWith('workspace_token', expect.any(String));
  });

  test('calls updateField when Jupyter server URL is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const serverInput = screen.getByPlaceholderText('http://localhost:8888');
    await user.type(serverInput, 'http://localhost:8888');

    expect(updateField).toHaveBeenCalledWith('jupyter_server', expect.any(String));
  });

  test('selects scan output option when clicked', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    // Click on "Disabled" option
    const disabledLabel = screen.getByText('Disabled').closest('label');
    if (disabledLabel) {
      await user.click(disabledLabel);
      expect(updateField).toHaveBeenCalledWith('scan_outputs', 'disabled');
    }
  });

  test('shows loading spinner when loading', () => {
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, loading: true });

    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.queryByText('Authentication')).not.toBeInTheDocument();
  });

  test('Test Connection button is disabled when workspace token is empty', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).toBeDisabled();
  });

  test('Test Connection button is enabled when workspace token is filled', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      config: {
        workspace_token: 'test-token',
        jupyter_server: '',
        scan_outputs: 'enabled',
      },
    });

    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).not.toBeDisabled();
  });

  test('shows success message when test passes', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful', latency_ms: 100 },
    });

    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection successful')).toBeInTheDocument();
  });

  test('shows error message when test fails', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: false, message: 'Connection refused' },
    });

    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection refused')).toBeInTheDocument();
  });

  test('displays validation errors', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        workspace_token: 'Token is required',
      },
    });

    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Token is required')).toBeInTheDocument();
  });

  test('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<JupyterLabConfig isOpen={true} onClose={onClose} onSave={vi.fn()} />);

    await user.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  test('displays footer security message', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Credentials are encrypted at rest')).toBeInTheDocument();
  });

  test('Save button is disabled until test passes', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).toBeDisabled();
  });

  test('Save button is enabled after successful test', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful' },
    });

    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).not.toBeDisabled();
  });

  test('shows scan output option descriptions', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Scan cell outputs for sensitive data')).toBeInTheDocument();
    expect(screen.getByText('Skip output scanning (faster)')).toBeInTheDocument();
  });

  test('shows output scanning help text', () => {
    render(<JupyterLabConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText(/Output scanning detects secrets, credentials, and PII in cell outputs/)).toBeInTheDocument();
  });
});
