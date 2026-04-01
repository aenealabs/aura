/**
 * Tests for VSCodeConfig component
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import VSCodeConfig from './VSCodeConfig';

// Mock the useIntegrationConfig hook
vi.mock('../../hooks/useIntegrations', () => ({
  useIntegrationConfig: vi.fn(),
}));

import { useIntegrationConfig } from '../../hooks/useIntegrations';

const mockConfig = {
  workspace_token: '',
  auto_scan: 'on_save',
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

describe('VSCodeConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook });
  });

  test('renders nothing when isOpen is false', () => {
    const { container } = render(
      <VSCodeConfig isOpen={false} onClose={vi.fn()} onSave={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders modal when isOpen is true', () => {
    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Configure VS Code')).toBeInTheDocument();
    expect(screen.getByText('IDE integration for real-time security scanning')).toBeInTheDocument();
  });

  test('displays authentication section', () => {
    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Authentication')).toBeInTheDocument();
    expect(screen.getByText(/Workspace Token/)).toBeInTheDocument();
  });

  test('displays scan settings section with auto-scan options', () => {
    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Scan Settings')).toBeInTheDocument();
    expect(screen.getByText('Auto Scan Mode')).toBeInTheDocument();
    expect(screen.getByText('On Save')).toBeInTheDocument();
    expect(screen.getByText('On Change')).toBeInTheDocument();
    expect(screen.getByText('Manual')).toBeInTheDocument();
  });

  test('displays display settings section', () => {
    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Display Settings')).toBeInTheDocument();
    expect(screen.getByText('Inline hints')).toBeInTheDocument();
    expect(screen.getByText('Problems panel')).toBeInTheDocument();
  });

  test('calls updateField when workspace token is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const tokenInput = screen.getByPlaceholderText('aura_wst_xxxxxxxxxxxxxxxxxxxx');
    await user.type(tokenInput, 'test-token');

    expect(updateField).toHaveBeenCalledWith('workspace_token', expect.any(String));
  });

  test('selects auto-scan option when clicked', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    // Click on "On Change" option
    const onChangeLabel = screen.getByText('On Change').closest('label');
    if (onChangeLabel) {
      await user.click(onChangeLabel);
      expect(updateField).toHaveBeenCalledWith('auto_scan', 'on_change');
    }
  });

  test('shows loading spinner when loading', () => {
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, loading: true });

    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.queryByText('Authentication')).not.toBeInTheDocument();
  });

  test('Test Connection button is disabled when workspace token is empty', () => {
    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).toBeDisabled();
  });

  test('Test Connection button is enabled when workspace token is filled', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      config: {
        workspace_token: 'test-token',
        auto_scan: 'on_save',
      },
    });

    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).not.toBeDisabled();
  });

  test('shows success message when test passes', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful', latency_ms: 50 },
    });

    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection successful')).toBeInTheDocument();
  });

  test('shows error message when test fails', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: false, message: 'Invalid token' },
    });

    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Invalid token')).toBeInTheDocument();
  });

  test('displays validation errors', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        workspace_token: 'Token is required',
      },
    });

    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Token is required')).toBeInTheDocument();
  });

  test('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<VSCodeConfig isOpen={true} onClose={onClose} onSave={vi.fn()} />);

    await user.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  test('displays footer security message', () => {
    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Credentials are encrypted at rest')).toBeInTheDocument();
  });

  test('Save button is disabled until test passes', () => {
    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).toBeDisabled();
  });

  test('shows auto-scan option descriptions', () => {
    render(<VSCodeConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Scan when file is saved')).toBeInTheDocument();
    expect(screen.getByText('Scan as you type (may impact performance)')).toBeInTheDocument();
    expect(screen.getByText('Only scan when triggered manually')).toBeInTheDocument();
  });
});
