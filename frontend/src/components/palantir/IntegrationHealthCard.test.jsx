/**
 * IntegrationHealthCard Tests
 *
 * Tests for the Palantir Integration Health Card component.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';
import { IntegrationHealthCard } from './IntegrationHealthCard';

describe('IntegrationHealthCard', () => {
  const mockHealthData = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    services: {
      ontology: 'ok',
      foundry: 'ok',
    },
  };

  const mockCircuitBreaker = {
    state: 'CLOSED',
    failure_count: 0,
    threshold: 5,
  };

  const mockSyncStatus = {
    ThreatActor: {
      objects_synced: 1500,
      last_sync_time: new Date().toISOString(),
      last_sync_status: 'synced',
    },
    Vulnerability: {
      objects_synced: 500,
      last_sync_time: new Date().toISOString(),
      last_sync_status: 'synced',
    },
  };

  test('renders loading skeleton when loading', () => {
    render(<IntegrationHealthCard isLoading />);

    // Check for skeleton animation class
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('renders error state', () => {
    render(<IntegrationHealthCard status="error" />);

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Unable to connect to Palantir')).toBeInTheDocument();
  });

  test('calls onRefresh when refresh button clicked', async () => {
    const user = userEvent.setup();
    const handleRefresh = vi.fn();

    render(
      <IntegrationHealthCard
        status="error"
        onRefresh={handleRefresh}
      />
    );

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });

  test('renders healthy state correctly', () => {
    render(
      <IntegrationHealthCard
        status="healthy"
        health={mockHealthData}
        circuitBreaker={mockCircuitBreaker}
        syncStatus={mockSyncStatus}
      />
    );

    expect(screen.getByText('Palantir AIP')).toBeInTheDocument();
    expect(screen.getByText('Healthy')).toBeInTheDocument();
  });

  test('renders degraded state when health is degraded', () => {
    const degradedHealth = { ...mockHealthData, status: 'degraded' };

    render(
      <IntegrationHealthCard
        status="degraded"
        health={degradedHealth}
        circuitBreaker={mockCircuitBreaker}
        syncStatus={mockSyncStatus}
      />
    );

    expect(screen.getByText('Degraded')).toBeInTheDocument();
  });

  test('renders error state when health is error', () => {
    const errorHealth = { ...mockHealthData, status: 'error' };

    render(
      <IntegrationHealthCard
        status="error"
        health={errorHealth}
        circuitBreaker={{ ...mockCircuitBreaker, state: 'OPEN' }}
        syncStatus={mockSyncStatus}
      />
    );

    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  test('displays sync status for each object type', () => {
    render(
      <IntegrationHealthCard
        status="healthy"
        health={mockHealthData}
        circuitBreaker={mockCircuitBreaker}
        syncStatus={mockSyncStatus}
      />
    );

    expect(screen.getByText('ThreatActor')).toBeInTheDocument();
    expect(screen.getByText('Vulnerability')).toBeInTheDocument();
    // Use more specific patterns to avoid matching "1,500" when looking for "500"
    expect(screen.getByText(/1,500 objects/)).toBeInTheDocument();
    expect(screen.getByText(/^500 objects/)).toBeInTheDocument();
  });

  test('displays circuit breaker indicator', () => {
    render(
      <IntegrationHealthCard
        status="healthy"
        health={mockHealthData}
        circuitBreaker={mockCircuitBreaker}
        syncStatus={mockSyncStatus}
      />
    );

    // CircuitBreakerIndicator shows the state label
    expect(screen.getByText('Operational')).toBeInTheDocument();
    // And has accessible role
    expect(screen.getByRole('region', { name: /circuit breaker/i })).toBeInTheDocument();
  });

  test('shows refresh button and calls onRefresh', async () => {
    const user = userEvent.setup();
    const handleRefresh = vi.fn();

    render(
      <IntegrationHealthCard
        status="healthy"
        health={mockHealthData}
        circuitBreaker={mockCircuitBreaker}
        syncStatus={mockSyncStatus}
        onRefresh={handleRefresh}
      />
    );

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });

  test('applies custom className', () => {
    const { container } = render(
      <IntegrationHealthCard
        status="healthy"
        health={mockHealthData}
        circuitBreaker={mockCircuitBreaker}
        syncStatus={mockSyncStatus}
        className="custom-class"
      />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('handles empty sync status gracefully', () => {
    render(
      <IntegrationHealthCard
        status="healthy"
        health={mockHealthData}
        circuitBreaker={mockCircuitBreaker}
        syncStatus={{}}
      />
    );

    expect(screen.getByText('Palantir AIP')).toBeInTheDocument();
  });

  test('shows last sync time in human readable format', () => {
    const recentTime = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // 5 minutes ago

    render(
      <IntegrationHealthCard
        status="healthy"
        health={mockHealthData}
        circuitBreaker={mockCircuitBreaker}
        lastSyncTime={recentTime}
        syncStatus={{
          ThreatActor: {
            objects_synced: 100,
            last_sync_time: recentTime,
            last_sync_status: 'synced',
          },
        }}
      />
    );

    expect(screen.getByText(/5 min ago|just now/i)).toBeInTheDocument();
  });
});
