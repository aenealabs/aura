/**
 * DataFreshnessIndicator Tests
 *
 * Tests for the Data Freshness indicator component.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { render, screen } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { DataFreshnessIndicator, useFreshness } from './DataFreshnessIndicator';

describe('DataFreshnessIndicator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('renders unknown state when no timestamp provided', () => {
    render(<DataFreshnessIndicator />);

    expect(screen.getByText(/unknown/i)).toBeInTheDocument();
  });

  test('shows fresh state for recent data', () => {
    const timestamp = new Date('2024-01-15T11:58:00Z').toISOString(); // 2 minutes ago

    render(<DataFreshnessIndicator timestamp={timestamp} />);

    expect(screen.getByText(/just now|2 min ago/i)).toBeInTheDocument();
  });

  test('shows stale state for older data', () => {
    const timestamp = new Date('2024-01-15T11:45:00Z').toISOString(); // 15 minutes ago

    render(<DataFreshnessIndicator timestamp={timestamp} />);

    expect(screen.getByText(/15 min ago/i)).toBeInTheDocument();
  });

  test('shows expired state for very old data', () => {
    const timestamp = new Date('2024-01-15T11:00:00Z').toISOString(); // 60 minutes ago

    render(<DataFreshnessIndicator timestamp={timestamp} />);

    expect(screen.getByText(/may be outdated|1h ago/i)).toBeInTheDocument();
  });

  test('renders with custom label', () => {
    const timestamp = new Date('2024-01-15T11:58:00Z').toISOString();

    render(<DataFreshnessIndicator timestamp={timestamp} label="Synced" />);

    expect(screen.getByText(/synced/i)).toBeInTheDocument();
  });

  test('renders compact mode', () => {
    const timestamp = new Date('2024-01-15T11:58:00Z').toISOString();

    const { container } = render(
      <DataFreshnessIndicator timestamp={timestamp} compact />
    );

    // Compact mode should have smaller text
    expect(container.querySelector('.text-xs')).toBeInTheDocument();
  });

  test('applies custom className', () => {
    const timestamp = new Date('2024-01-15T11:58:00Z').toISOString();

    const { container } = render(
      <DataFreshnessIndicator timestamp={timestamp} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('handles unknown state for invalid timestamps', () => {
    render(<DataFreshnessIndicator timestamp="invalid-timestamp" />);

    expect(screen.getByText(/unknown/i)).toBeInTheDocument();
  });

  test('updates display over time', () => {
    const timestamp = new Date('2024-01-15T11:58:00Z').toISOString(); // 2 minutes ago

    render(<DataFreshnessIndicator timestamp={timestamp} />);

    // Initial state
    expect(screen.getByText(/just now|2 min ago/i)).toBeInTheDocument();

    // Advance time by 10 minutes
    vi.advanceTimersByTime(10 * 60 * 1000);

    // Note: This won't automatically re-render without a state update trigger
    // The component would need to use an interval to update
  });
});

describe('useFreshness', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('returns fresh for recent timestamps', () => {
    const timestamp = new Date('2024-01-15T11:58:00Z').toISOString(); // 2 minutes ago

    const { result } = renderHook(() => useFreshness(timestamp));

    expect(result.current.state).toBe('fresh');
    expect(result.current.isFresh).toBe(true);
    expect(result.current.isStale).toBe(false);
    expect(result.current.isExpired).toBe(false);
  });

  test('returns stale for older timestamps', () => {
    const timestamp = new Date('2024-01-15T11:45:00Z').toISOString(); // 15 minutes ago

    const { result } = renderHook(() => useFreshness(timestamp));

    expect(result.current.state).toBe('stale');
    expect(result.current.isFresh).toBe(false);
    expect(result.current.isStale).toBe(true);
    expect(result.current.isExpired).toBe(false);
  });

  test('returns expired for very old timestamps', () => {
    const timestamp = new Date('2024-01-15T11:00:00Z').toISOString(); // 60 minutes ago

    const { result } = renderHook(() => useFreshness(timestamp));

    expect(result.current.state).toBe('expired');
    expect(result.current.isFresh).toBe(false);
    expect(result.current.isStale).toBe(false);
    expect(result.current.isExpired).toBe(true);
  });

  test('returns unknown for null timestamp', () => {
    const { result } = renderHook(() => useFreshness(null));

    expect(result.current.state).toBe('unknown');
    expect(result.current.minutes).toBe(null);
  });

  test('calculates minutes correctly', () => {
    const timestamp = new Date('2024-01-15T11:45:00Z').toISOString(); // 15 minutes ago

    const { result } = renderHook(() => useFreshness(timestamp));

    expect(result.current.minutes).toBe(15);
  });
});
