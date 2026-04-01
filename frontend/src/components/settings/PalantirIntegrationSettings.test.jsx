/**
 * PalantirIntegrationSettings Tests
 *
 * Tests for the Palantir AIP Integration Settings wizard component.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { PalantirIntegrationSettings } from './PalantirIntegrationSettings';
import * as palantirApi from '../../services/palantirApi';

vi.mock('../../services/palantirApi');

describe('PalantirIntegrationSettings', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSave: vi.fn(),
    onSuccess: vi.fn(),
    onError: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // Rendering Tests
  describe('Rendering', () => {
    test('renders nothing when isOpen is false', () => {
      const { container } = render(
        <PalantirIntegrationSettings {...defaultProps} isOpen={false} />
      );

      expect(container.firstChild).toBeNull();
    });

    test('renders modal when isOpen is true', () => {
      render(<PalantirIntegrationSettings {...defaultProps} />);

      expect(screen.getByText('Configure Palantir AIP Integration')).toBeInTheDocument();
    });

    test('renders step indicator with 5 steps', () => {
      render(<PalantirIntegrationSettings {...defaultProps} />);

      expect(screen.getByText('Connection')).toBeInTheDocument();
      expect(screen.getByText('Authentication')).toBeInTheDocument();
      expect(screen.getByText('Data Mapping')).toBeInTheDocument();
      expect(screen.getByText('Event Stream')).toBeInTheDocument();
      expect(screen.getByText('Review & Enable')).toBeInTheDocument();
    });

    test('renders with edit title when existingConfig provided', () => {
      render(
        <PalantirIntegrationSettings
          {...defaultProps}
          existingConfig={{ ontology_url: 'https://test.com' }}
        />
      );

      expect(screen.getByText('Edit Palantir AIP Integration')).toBeInTheDocument();
    });
  });

  // Step 1: Connection Tests
  describe('Step 1: Connection', () => {
    test('renders connection form fields', () => {
      render(<PalantirIntegrationSettings {...defaultProps} />);

      // Use placeholder text to find inputs
      expect(screen.getByPlaceholderText(/your-instance\.palantirfoundry\.com\/ontology/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText('https://your-instance.palantirfoundry.com')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('production')).toBeInTheDocument();
    });

    test('validates required fields before advancing', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      // Try to advance without filling required fields
      await user.click(screen.getByRole('button', { name: /next/i }));

      expect(screen.getByText(/ontology url is required/i)).toBeInTheDocument();
      expect(screen.getByText(/foundry url is required/i)).toBeInTheDocument();
    });

    test('advances to step 2 when valid', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      // Fill required fields using placeholder
      await user.type(
        screen.getByPlaceholderText(/your-instance\.palantirfoundry\.com\/ontology/i),
        'https://test.palantir.com/ontology'
      );
      await user.type(
        screen.getByPlaceholderText('https://your-instance.palantirfoundry.com'),
        'https://test.palantir.com'
      );

      await user.click(screen.getByRole('button', { name: /next/i }));

      // Should now be on Authentication step
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/enter your palantir api key/i)).toBeInTheDocument();
      });
    });
  });

  // Step 2: Authentication Tests
  describe('Step 2: Authentication', () => {
    async function advanceToStep2(user) {
      await user.type(
        screen.getByPlaceholderText(/your-instance\.palantirfoundry\.com\/ontology/i),
        'https://test.palantir.com/ontology'
      );
      await user.type(
        screen.getByPlaceholderText('https://your-instance.palantirfoundry.com'),
        'https://test.palantir.com'
      );
      await user.click(screen.getByRole('button', { name: /next/i }));
    }

    test('renders authentication form fields', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep2(user);

      expect(screen.getByPlaceholderText(/enter your palantir api key/i)).toBeInTheDocument();
      expect(screen.getByText(/mtls certificate/i)).toBeInTheDocument();
    });

    test('validates API key before advancing', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep2(user);
      await user.click(screen.getByRole('button', { name: /next/i }));

      expect(screen.getByText(/api key is required/i)).toBeInTheDocument();
    });

    test('test connection button calls API', async () => {
      const user = userEvent.setup();
      palantirApi.testConnection.mockResolvedValue({ success: true, latency_ms: 150 });

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep2(user);
      await user.type(screen.getByPlaceholderText(/enter your palantir api key/i), 'test-api-key');
      await user.click(screen.getByRole('button', { name: /test connection/i }));

      await waitFor(() => {
        expect(palantirApi.testConnection).toHaveBeenCalled();
      });
    });

    test('displays test connection success', async () => {
      const user = userEvent.setup();
      palantirApi.testConnection.mockResolvedValue({ success: true, latency_ms: 150 });

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep2(user);
      await user.type(screen.getByPlaceholderText(/enter your palantir api key/i), 'test-api-key');
      await user.click(screen.getByRole('button', { name: /test connection/i }));

      await waitFor(() => {
        expect(screen.getByText(/connection successful/i)).toBeInTheDocument();
        expect(screen.getByText(/150ms/)).toBeInTheDocument();
      });
    });

    test('displays test connection failure', async () => {
      const user = userEvent.setup();
      palantirApi.testConnection.mockResolvedValue({ success: false, error: 'Invalid API key' });

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep2(user);
      await user.type(screen.getByPlaceholderText(/enter your palantir api key/i), 'invalid-key');
      await user.click(screen.getByRole('button', { name: /test connection/i }));

      await waitFor(() => {
        expect(screen.getByText(/connection failed/i)).toBeInTheDocument();
      });
    });
  });

  // Step 3: Data Mapping Tests
  describe('Step 3: Data Mapping', () => {
    async function advanceToStep3(user) {
      await user.type(
        screen.getByPlaceholderText(/your-instance\.palantirfoundry\.com\/ontology/i),
        'https://test.palantir.com/ontology'
      );
      await user.type(
        screen.getByPlaceholderText('https://your-instance.palantirfoundry.com'),
        'https://test.palantir.com'
      );
      await user.click(screen.getByRole('button', { name: /next/i }));
      await user.type(screen.getByPlaceholderText(/enter your palantir api key/i), 'test-api-key');
      await user.click(screen.getByRole('button', { name: /next/i }));
    }

    test('renders object type checkboxes', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep3(user);

      expect(screen.getByText('Threat Intelligence')).toBeInTheDocument();
      expect(screen.getByText('Asset CMDB')).toBeInTheDocument();
      expect(screen.getByText('Compliance Controls')).toBeInTheDocument();
    });

    test('allows toggling object types', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep3(user);

      const insiderRisk = screen.getByText('Insider Risk Indicators').closest('button');
      await user.click(insiderRisk);

      // Should toggle selection state
      expect(insiderRisk.className).toContain('border-aura');
    });

    test('renders sync frequency selector', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep3(user);

      expect(screen.getByText(/sync frequency/i)).toBeInTheDocument();
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });
  });

  // Step 4: Event Stream Tests
  describe('Step 4: Event Stream', () => {
    async function advanceToStep4(user) {
      await user.type(
        screen.getByPlaceholderText(/your-instance\.palantirfoundry\.com\/ontology/i),
        'https://test.palantir.com/ontology'
      );
      await user.type(
        screen.getByPlaceholderText('https://your-instance.palantirfoundry.com'),
        'https://test.palantir.com'
      );
      await user.click(screen.getByRole('button', { name: /next/i }));
      await user.type(screen.getByPlaceholderText(/enter your palantir api key/i), 'test-api-key');
      await user.click(screen.getByRole('button', { name: /next/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));
    }

    test('renders event target options', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep4(user);

      expect(screen.getByText('AWS EventBridge')).toBeInTheDocument();
      expect(screen.getByText('Apache Kafka')).toBeInTheDocument();
      expect(screen.getByText('AWS SQS')).toBeInTheDocument();
    });

    test('renders event type checkboxes', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep4(user);

      expect(screen.getByText('New Threats')).toBeInTheDocument();
      expect(screen.getByText('Threat Updates')).toBeInTheDocument();
      expect(screen.getByText('Compliance Drift')).toBeInTheDocument();
    });

    test('shows Kafka config when Kafka selected', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep4(user);

      await user.click(screen.getByText('Apache Kafka'));

      expect(screen.getByText(/kafka configuration/i)).toBeInTheDocument();
      expect(screen.getByText(/bootstrap servers/i)).toBeInTheDocument();
    });

    test('shows EventBridge config when EventBridge selected', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep4(user);

      await user.click(screen.getByText('AWS EventBridge'));

      expect(screen.getByText(/eventbridge configuration/i)).toBeInTheDocument();
    });
  });

  // Step 5: Review Tests
  describe('Step 5: Review', () => {
    async function advanceToStep5(user) {
      await user.type(
        screen.getByPlaceholderText(/your-instance\.palantirfoundry\.com\/ontology/i),
        'https://test.palantir.com/ontology'
      );
      await user.type(
        screen.getByPlaceholderText('https://your-instance.palantirfoundry.com'),
        'https://test.palantir.com'
      );
      await user.click(screen.getByRole('button', { name: /next/i }));
      await user.type(screen.getByPlaceholderText(/enter your palantir api key/i), 'test-api-key');
      await user.click(screen.getByRole('button', { name: /next/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));
    }

    test('renders configuration summary', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep5(user);

      expect(screen.getByText('Review Configuration')).toBeInTheDocument();
      // Multiple elements match /connection/i (step indicator + summary section), verify at least exists
      expect(screen.getAllByText(/connection/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/data mapping/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/event stream/i).length).toBeGreaterThan(0);
    });

    test('displays consent checkbox', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep5(user);

      expect(screen.getByRole('checkbox')).toBeInTheDocument();
      expect(screen.getByText(/i understand/i)).toBeInTheDocument();
    });

    test('enable button disabled without consent', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep5(user);

      const enableButton = screen.getByRole('button', { name: /enable integration/i });
      expect(enableButton).toBeDisabled();
    });

    test('enable button enabled with consent', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await advanceToStep5(user);

      await user.click(screen.getByRole('checkbox'));

      const enableButton = screen.getByRole('button', { name: /enable integration/i });
      expect(enableButton).not.toBeDisabled();
    });

    test('calls onSave when enabled', async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue({});

      render(<PalantirIntegrationSettings {...defaultProps} onSave={onSave} />);

      await advanceToStep5(user);

      await user.click(screen.getByRole('checkbox'));
      await user.click(screen.getByRole('button', { name: /enable integration/i }));

      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
          ontology_url: 'https://test.palantir.com/ontology',
          foundry_url: 'https://test.palantir.com',
          api_key: 'test-api-key',
        }));
      });
    });

    test('calls onSuccess after save', async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue({});
      const onSuccess = vi.fn();

      render(<PalantirIntegrationSettings {...defaultProps} onSave={onSave} onSuccess={onSuccess} />);

      await advanceToStep5(user);

      await user.click(screen.getByRole('checkbox'));
      await user.click(screen.getByRole('button', { name: /enable integration/i }));

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith('Palantir AIP integration enabled');
      });
    });

    test('calls onError on save failure', async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockRejectedValue(new Error('Save failed'));
      const onError = vi.fn();

      render(<PalantirIntegrationSettings {...defaultProps} onSave={onSave} onError={onError} />);

      await advanceToStep5(user);

      await user.click(screen.getByRole('checkbox'));
      await user.click(screen.getByRole('button', { name: /enable integration/i }));

      await waitFor(() => {
        expect(onError).toHaveBeenCalled();
      });
    });
  });

  // Navigation Tests
  describe('Navigation', () => {
    test('back button goes to previous step', async () => {
      const user = userEvent.setup();

      render(<PalantirIntegrationSettings {...defaultProps} />);

      await user.type(
        screen.getByPlaceholderText(/your-instance\.palantirfoundry\.com\/ontology/i),
        'https://test.palantir.com/ontology'
      );
      await user.type(
        screen.getByPlaceholderText('https://your-instance.palantirfoundry.com'),
        'https://test.palantir.com'
      );
      await user.click(screen.getByRole('button', { name: /next/i }));

      // Now on step 2
      expect(screen.getByPlaceholderText(/enter your palantir api key/i)).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: /back/i }));

      // Back to step 1
      expect(screen.getByPlaceholderText(/your-instance\.palantirfoundry\.com\/ontology/i)).toBeInTheDocument();
    });

    test('cancel button calls onClose on first step', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      render(<PalantirIntegrationSettings {...defaultProps} onClose={onClose} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onClose).toHaveBeenCalled();
    });

    test('close button calls onClose', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      render(<PalantirIntegrationSettings {...defaultProps} onClose={onClose} />);

      // Close button is the X icon button - find it by looking for the button with the XMarkIcon
      const buttons = screen.getAllByRole('button');
      const closeButton = buttons.find(btn => btn.querySelector('svg.w-5.h-5'));
      await user.click(closeButton);

      expect(onClose).toHaveBeenCalled();
    });
  });
});
