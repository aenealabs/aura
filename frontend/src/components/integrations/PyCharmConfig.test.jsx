/**
 * Tests for PyCharmConfig component
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import PyCharmConfig from './PyCharmConfig';

// Mock the useIntegrationConfig hook
vi.mock('../../hooks/useIntegrations', () => ({
  useIntegrationConfig: vi.fn(),
}));

import { useIntegrationConfig } from '../../hooks/useIntegrations';

const mockConfig = {
  workspace_token: '',
  python_interpreter: '',
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

describe('PyCharmConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook });
  });

  test('renders nothing when isOpen is false', () => {
    const { container } = render(
      <PyCharmConfig isOpen={false} onClose={vi.fn()} onSave={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders modal when isOpen is true', () => {
    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Configure PyCharm')).toBeInTheDocument();
    expect(screen.getByText('JetBrains IDE integration for Python development')).toBeInTheDocument();
  });

  test('displays authentication section', () => {
    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Authentication')).toBeInTheDocument();
    expect(screen.getByText(/Workspace Token/)).toBeInTheDocument();
  });

  test('displays Python settings section', () => {
    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Python Settings')).toBeInTheDocument();
    expect(screen.getByText('Python Interpreter Path')).toBeInTheDocument();
  });

  test('displays analysis settings section', () => {
    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Analysis Settings')).toBeInTheDocument();
    expect(screen.getByText('Auto scan on save')).toBeInTheDocument();
    expect(screen.getByText('Type checking')).toBeInTheDocument();
    expect(screen.getByText('Code inspections')).toBeInTheDocument();
  });

  test('calls updateField when workspace token is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const tokenInput = screen.getByPlaceholderText('aura_wst_xxxxxxxxxxxxxxxxxxxx');
    await user.type(tokenInput, 'test-token');

    expect(updateField).toHaveBeenCalledWith('workspace_token', expect.any(String));
  });

  test('calls updateField when Python interpreter is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const interpreterInput = screen.getByPlaceholderText('/usr/bin/python3 or venv/bin/python');
    await user.type(interpreterInput, '/usr/bin/python3');

    expect(updateField).toHaveBeenCalledWith('python_interpreter', expect.any(String));
  });

  test('shows loading spinner when loading', () => {
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, loading: true });

    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.queryByText('Authentication')).not.toBeInTheDocument();
  });

  test('Test Connection button is disabled when workspace token is empty', () => {
    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).toBeDisabled();
  });

  test('Test Connection button is enabled when workspace token is filled', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      config: {
        workspace_token: 'test-token',
        python_interpreter: '',
      },
    });

    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const testButton = screen.getByRole('button', { name: /test/i });
    expect(testButton).not.toBeDisabled();
  });

  test('shows success message when test passes', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful', latency_ms: 75 },
    });

    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection successful')).toBeInTheDocument();
  });

  test('shows error message when test fails', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: false, message: 'Invalid token' },
    });

    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Invalid token')).toBeInTheDocument();
  });

  test('displays validation errors', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        workspace_token: 'Token is required',
      },
    });

    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Token is required')).toBeInTheDocument();
  });

  test('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<PyCharmConfig isOpen={true} onClose={onClose} onSave={vi.fn()} />);

    await user.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  test('displays footer security message', () => {
    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Credentials are encrypted at rest')).toBeInTheDocument();
  });

  test('Save button is disabled until test passes', () => {
    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).toBeDisabled();
  });

  test('Save button is enabled after successful test', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful' },
    });

    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).not.toBeDisabled();
  });

  test('shows helper text for Python interpreter', () => {
    render(<PyCharmConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText(/Optional: Path to Python interpreter for accurate analysis/)).toBeInTheDocument();
  });
});
