/**
 * SyncStatusWidget Tests
 *
 * Tests for the Ontology Sync Status Widget component.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { SyncStatusWidget } from './SyncStatusWidget';
import * as usePalantirSyncModule from '../../../hooks/usePalantirSync';

vi.mock('../../../hooks/usePalantirSync');

describe('SyncStatusWidget', () => {
  // Actual mock data uses ThreatActor, Vulnerability, Asset, Compliance
  const mockSyncStatus = {
    ThreatActor: {
      object_type: 'ThreatActor',
      objects_synced: 247,
      last_sync_time: new Date().toISOString(),
      last_sync_status: 'synced',
    },
    Vulnerability: {
      object_type: 'Vulnerability',
      objects_synced: 1892,
      last_sync_time: new Date().toISOString(),
      last_sync_status: 'synced',
    },
    Asset: {
      object_type: 'Asset',
      objects_synced: 156,
      last_sync_time: new Date(Date.now() - 3600000).toISOString(),
      last_sync_status: 'pending',
    },
    Compliance: {
      object_type: 'Compliance',
      objects_synced: 892,
      last_sync_time: null,
      last_sync_status: 'failed',
    },
  };

  const mockCircuitBreaker = {
    state: 'CLOSED',
    failure_count: 0,
    threshold: 5,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test('renders loading skeleton initially', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: null,
      circuitBreaker: null,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    });

    render(<SyncStatusWidget />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('renders sync status after loading', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: mockSyncStatus,
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: new Date().toISOString(),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SyncStatusWidget />);

    expect(screen.getByText('Ontology Sync Health')).toBeInTheDocument();
    expect(screen.getByText('ThreatActor')).toBeInTheDocument();
    expect(screen.getByText('Vulnerability')).toBeInTheDocument();
  });

  test('displays object counts', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: mockSyncStatus,
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: new Date().toISOString(),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SyncStatusWidget />);

    expect(screen.getByText('247')).toBeInTheDocument();
    expect(screen.getByText('1,892')).toBeInTheDocument();
  });

  test('displays sync status icons', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: mockSyncStatus,
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: new Date().toISOString(),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    const { container } = render(<SyncStatusWidget />);

    // Should have check icons for synced status
    expect(container.querySelectorAll('.text-green-500').length).toBeGreaterThan(0);
  });

  test('renders error state when fetch fails', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: null,
      circuitBreaker: null,
      isLoading: false,
      error: new Error('Failed to load'),
      refetch: vi.fn(),
    });

    render(<SyncStatusWidget />);

    expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
  });

  test('retry button calls refetch', async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();

    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: null,
      circuitBreaker: null,
      isLoading: false,
      error: new Error('Failed'),
      refetch,
    });

    render(<SyncStatusWidget />);

    const retryButton = screen.getByRole('button', { name: /retry/i });
    await user.click(retryButton);

    expect(refetch).toHaveBeenCalled();
  });

  test('displays circuit breaker indicator when showCircuitBreaker is true', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: mockSyncStatus,
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: new Date().toISOString(),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SyncStatusWidget showCircuitBreaker />);

    expect(screen.getByText(/circuit breaker/i)).toBeInTheDocument();
  });

  test('hides circuit breaker when showCircuitBreaker is false', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: mockSyncStatus,
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: new Date().toISOString(),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SyncStatusWidget showCircuitBreaker={false} />);

    expect(screen.queryByText(/circuit breaker/i)).not.toBeInTheDocument();
  });

  test('refresh button calls refetch', async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();

    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: mockSyncStatus,
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: new Date().toISOString(),
      isLoading: false,
      error: null,
      refetch,
    });

    render(<SyncStatusWidget />);

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    expect(refetch).toHaveBeenCalled();
  });

  test('displays relative sync times', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: mockSyncStatus,
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: new Date().toISOString(),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SyncStatusWidget />);

    // Multiple sync times are displayed (one per object type)
    const syncTimeElements = screen.getAllByText(/just now|min ago/i);
    expect(syncTimeElements.length).toBeGreaterThan(0);
  });

  test('shows empty state when no sync data', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: {},
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: null,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SyncStatusWidget />);

    expect(screen.getByText(/no sync data/i)).toBeInTheDocument();
  });

  test('applies custom className', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: mockSyncStatus,
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: new Date().toISOString(),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    const { container } = render(<SyncStatusWidget className="custom-class" />);

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('has proper accessibility attributes', () => {
    usePalantirSyncModule.usePalantirSync.mockReturnValue({
      syncStatus: mockSyncStatus,
      circuitBreaker: mockCircuitBreaker,
      lastSyncTime: new Date().toISOString(),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SyncStatusWidget />);

    expect(screen.getByRole('region', { name: /ontology sync health/i })).toBeInTheDocument();
  });
});
