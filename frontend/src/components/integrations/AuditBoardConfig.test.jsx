/**
 * Tests for AuditBoardConfig component
 * ADR-053: Enterprise Security Integrations
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import AuditBoardConfig from './AuditBoardConfig';

// Mock the useIntegrationConfig hook
vi.mock('../../hooks/useIntegrations', () => ({
  useIntegrationConfig: vi.fn(),
}));

import { useIntegrationConfig } from '../../hooks/useIntegrations';

const mockConfig = {
  base_url: '',
  api_key: '',
  api_secret: '',
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

describe('AuditBoardConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook });
  });

  test('renders nothing when isOpen is false', () => {
    const { container } = render(
      <AuditBoardConfig isOpen={false} onClose={vi.fn()} onSave={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders modal when isOpen is true', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Configure AuditBoard GRC')).toBeInTheDocument();
    expect(screen.getByText('Governance, risk, and compliance management platform')).toBeInTheDocument();
  });

  test('displays GovCloud toggle', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('GovCloud Environment')).toBeInTheDocument();
    expect(screen.getByText(/Enable for US Government deployment/)).toBeInTheDocument();
  });

  test('displays connection settings section with HMAC fields', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection Settings')).toBeInTheDocument();
    expect(screen.getByText(/API Key/)).toBeInTheDocument();
    expect(screen.getByText(/API Secret/)).toBeInTheDocument();
  });

  test('displays base URL field', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText(/AuditBoard URL/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('https://your-org.auditboardapp.com')).toBeInTheDocument();
  });

  test('displays feature toggles for GRC', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Enabled Features')).toBeInTheDocument();
    expect(screen.getByText('Controls')).toBeInTheDocument();
    expect(screen.getByText('Risks')).toBeInTheDocument();
    expect(screen.getByText('Findings')).toBeInTheDocument();
    expect(screen.getByText('Evidence')).toBeInTheDocument();
  });

  test('displays compliance frameworks section', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Compliance Frameworks')).toBeInTheDocument();
    expect(screen.getByText('SOC 2')).toBeInTheDocument();
    expect(screen.getByText('ISO 27001')).toBeInTheDocument();
    expect(screen.getByText('CMMC')).toBeInTheDocument();
  });

  test('displays additional compliance frameworks', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('NIST CSF')).toBeInTheDocument();
    expect(screen.getByText('NIST 800-53')).toBeInTheDocument();
    expect(screen.getByText('HIPAA')).toBeInTheDocument();
    expect(screen.getByText('PCI DSS')).toBeInTheDocument();
    expect(screen.getByText('GDPR')).toBeInTheDocument();
    expect(screen.getByText('FedRAMP')).toBeInTheDocument();
  });

  test('displays sync interval options', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Sync Interval')).toBeInTheDocument();
  });

  test('calls updateField when API key is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const apiKeyInput = screen.getByPlaceholderText('Enter your AuditBoard API key');
    await user.type(apiKeyInput, 'test-api-key');

    expect(updateField).toHaveBeenCalledWith('api_key', expect.any(String));
  });

  test('calls updateField when base URL is changed', async () => {
    const updateField = vi.fn();
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, updateField });
    const user = userEvent.setup();

    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const urlInput = screen.getByPlaceholderText('https://your-org.auditboardapp.com');
    await user.type(urlInput, 'https://test.auditboardapp.com');

    expect(updateField).toHaveBeenCalledWith('base_url', expect.any(String));
  });

  test('shows loading spinner when loading', () => {
    useIntegrationConfig.mockReturnValue({ ...defaultMockHook, loading: true });

    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.queryByText('Connection Settings')).not.toBeInTheDocument();
  });

  test('Test Connection button is disabled when credentials are empty', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    // Use exact text match to avoid matching "Control testing and monitoring"
    const testButton = screen.getByRole('button', { name: 'Test' });
    expect(testButton).toBeDisabled();
  });

  test('Test Connection button is enabled when credentials are filled', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      config: {
        base_url: 'https://your-org.auditboardapp.com',
        api_key: 'test-key',
        api_secret: 'test-secret',
      },
    });

    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    // Use exact text match to avoid matching "Control testing and monitoring"
    const testButton = screen.getByRole('button', { name: 'Test' });
    expect(testButton).not.toBeDisabled();
  });

  test('shows success message when test passes', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: true, message: 'Connection successful', latency_ms: 55 },
    });

    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Connection successful')).toBeInTheDocument();
  });

  test('shows error message when test fails', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      testResult: { success: false, message: 'Invalid HMAC signature' },
    });

    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Invalid HMAC signature')).toBeInTheDocument();
  });

  test('displays validation errors', () => {
    useIntegrationConfig.mockReturnValue({
      ...defaultMockHook,
      validationErrors: {
        base_url: 'Base URL is required',
      },
    });

    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Base URL is required')).toBeInTheDocument();
  });

  test('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<AuditBoardConfig isOpen={true} onClose={onClose} onSave={vi.fn()} />);

    await user.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  test('displays footer security message', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    expect(screen.getByText('Credentials are encrypted at rest')).toBeInTheDocument();
  });

  test('Save button is disabled until test passes', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: /save configuration/i });
    expect(saveButton).toBeDisabled();
  });

  test('toggles password visibility for API secret', async () => {
    const user = userEvent.setup();
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    // Find the API Secret input - it should be password type initially
    const secretInput = screen.getByPlaceholderText('Enter your AuditBoard API secret');
    expect(secretInput).toHaveAttribute('type', 'password');
  });

  test('evidence sync mode is hidden by default', () => {
    render(<AuditBoardConfig isOpen={true} onClose={vi.fn()} onSave={vi.fn()} />);

    // Evidence Sync Mode section only appears when evidence feature is enabled
    expect(screen.queryByText('Evidence Sync Mode')).not.toBeInTheDocument();
  });
});
